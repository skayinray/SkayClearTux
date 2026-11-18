"""Discord Rich Presence для SkayClearTux.

Собственная реализация Discord IPC — без сторонних библиотек.
Работает через Unix-сокет (Linux/macOS) и именованные каналы Windows
(`\\\\.\\pipe\\discord-ipc-N`), поэтому активность видна на всех платформах.

Активность привязана к открытому соединению и исчезает, когда SkayClearTux
закрывается. Нужен Application ID приложения Discord (раздел «Настройки»).
"""
from __future__ import annotations

import json
import os
import socket
import struct
import sys
import threading
import time

# Можно «зашить» свой Application ID сюда, чтобы активность работала из коробки.
BUILTIN_CLIENT_ID = ""

OP_HANDSHAKE = 0
OP_FRAME = 1
OP_CLOSE = 2
OP_PING = 3
OP_PONG = 4


def resolve_client_id(configured: str | None = None) -> str:
    """ID приложения: явно заданный в настройках или встроенный по умолчанию."""
    value = str(configured or "").strip()
    if value.isdigit():
        return value
    return BUILTIN_CLIENT_ID if BUILTIN_CLIENT_ID.isdigit() else ""


def _socket_candidates() -> list[str]:
    """Пути к IPC-сокету Discord (обычная установка, Flatpak, Snap)."""
    dirs: list[str] = []
    for env in ("XDG_RUNTIME_DIR", "TMPDIR", "TMP", "TEMP"):
        value = os.environ.get(env)
        if value:
            dirs.append(value)
    try:
        dirs.append(f"/run/user/{os.getuid()}")
    except Exception:  # noqa: BLE001
        pass
    dirs.append("/tmp")

    paths: list[str] = []
    for base in dirs:
        for sub in ("", "app/com.discordapp.Discord", "snap.discord",
                    "app/com.discordapp.DiscordCanary", "snap.discord-canary"):
            root = os.path.join(base, sub) if sub else base
            for i in range(10):
                paths.append(os.path.join(root, f"discord-ipc-{i}"))
    seen: set[str] = set()
    result: list[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


class _PipeTransport:
    """Обёртка над именованным каналом Windows (\\\\.\\pipe\\discord-ipc-N)."""

    def __init__(self, path: str):
        self.path = path
        self.file = open(path, "r+b", buffering=0)

    def _handle(self):
        import msvcrt
        return msvcrt.get_osfhandle(self.file.fileno())

    def sendall(self, data: bytes) -> None:
        self.file.write(data)
        self.file.flush()

    def recv_exact(self, count: int, timeout: float | None) -> bytes | None:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        buf = bytearray()
        deadline = None if timeout is None else (time.monotonic() + timeout)
        while len(buf) < count:
            if deadline is not None and time.monotonic() >= deadline:
                return None
            avail = ctypes.c_ulong(0)
            try:
                ok = kernel32.PeekNamedPipe(
                    self._handle(), None, 0, None,
                    ctypes.byref(avail), None)
            except Exception:  # noqa: BLE001
                return None
            if not ok:
                return None
            need = count - len(buf)
            if avail.value <= 0:
                time.sleep(0.05)
                continue
            try:
                chunk = self.file.read(min(need, int(avail.value) or need))
            except OSError:
                return None
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)

    def close(self) -> None:
        try:
            self.file.close()
        except OSError:
            pass


class _SocketTransport:
    def __init__(self, sock: socket.socket):
        self.sock = sock

    def sendall(self, data: bytes) -> None:
        self.sock.sendall(data)

    def recv_exact(self, count: int, timeout: float | None) -> bytes | None:
        if timeout is not None:
            self.sock.settimeout(timeout)
        buf = b""
        while len(buf) < count:
            try:
                chunk = self.sock.recv(count - len(buf))
            except TimeoutError:
                return None
            except OSError:
                return None
            if not chunk:
                return None
            buf += chunk
        return buf

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class DiscordIPC:
    """Минимальный клиент Discord IPC (Unix-сокеты и Windows named pipes)."""

    def __init__(self, client_id: str):
        self.client_id = resolve_client_id(client_id)
        self._transport = None

    @property
    def connected(self) -> bool:
        return self._transport is not None

    # ------------------------------------------------------------- транспорт
    def _send(self, op: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        assert self._transport is not None
        self._transport.sendall(struct.pack("<ii", op, len(data)) + data)

    def _recv(self, timeout: float | None = None):
        if self._transport is None:
            return None
        header = self._transport.recv_exact(8, timeout)
        if header is None:
            return None
        op, length = struct.unpack("<ii", header)
        if length <= 0:
            return op, None
        body = self._transport.recv_exact(length, timeout)
        if body is None:
            return None
        try:
            return op, json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return op, None

    # ------------------------------------------------------------------ API
    def connect(self) -> bool:
        if self.connected:
            return True
        if not self.client_id.isdigit():
            return False

        # Windows: именованные каналы Discord
        if sys.platform == "win32":
            for i in range(10):
                path = rf"\\.\pipe\discord-ipc-{i}"
                try:
                    pipe = _PipeTransport(path)
                    self._transport = pipe
                    self._send(OP_HANDSHAKE, {"v": 1, "client_id": self.client_id})
                    reply = self._recv(2.0)
                    if reply is None:
                        raise OSError("нет ответа на рукопожатие")
                    return True
                except OSError:
                    self._safe_close()
            return False

        # Linux / macOS: Unix domain sockets
        for path in _socket_candidates():
            if not os.path.exists(path):
                continue
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(2.0)
                s.connect(path)
                self._transport = _SocketTransport(s)
                self._send(OP_HANDSHAKE, {"v": 1, "client_id": self.client_id})
                reply = self._recv(2.0)
                if reply is None:
                    raise OSError("нет ответа на рукопожатие")
                s.settimeout(None)
                return True
            except OSError:
                self._safe_close()
        return False

    def set_activity(self, **activity) -> bool:
        if self._transport is None and not self.connect():
            return False
        payload = {
            "cmd": "SET_ACTIVITY",
            "args": {"pid": os.getpid(), "activity": activity},
            "nonce": f"{time.time():.6f}",
        }
        try:
            self._send(OP_FRAME, payload)
            # читаем ответ, попутно отвечая на ping
            for _ in range(3):
                reply = self._recv(1.5)
                if reply is None:
                    return False
                op, _data = reply
                if op == OP_PING:
                    self._send(OP_PONG, {})
                    continue
                return op == OP_FRAME
            return True
        except OSError:
            self._safe_close()
            return False

    def clear(self) -> None:
        if self._transport is None:
            return
        try:
            self._send(OP_FRAME, {
                "cmd": "SET_ACTIVITY",
                "args": {"pid": os.getpid()},
                "nonce": f"{time.time():.6f}",
            })
        except OSError:
            pass

    def _safe_close(self) -> None:
        if self._transport is not None:
            try:
                self._transport.close()
            except OSError:
                pass
        self._transport = None

    def close(self) -> None:
        self._safe_close()


class DiscordPresence:
    """Фоновый поток, который держит активность Discord в актуальном состоянии."""

    def __init__(self, client_id: str):
        self.client_id = resolve_client_id(client_id)
        self._ipc: DiscordIPC | None = None
        self._pending: tuple[str, str] | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_ts = int(time.time())
        self._last_ok = False

    @property
    def available(self) -> bool:
        return self.client_id.isdigit()

    def start(self) -> None:
        if not self.available:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._ipc is not None:
            self._ipc.clear()
            self._ipc.close()
            self._ipc = None

    def update(self, details: str, state: str) -> None:
        if not self.available:
            return
        with self._lock:
            self._pending = (details[:128], state[:128])

    def _run(self) -> None:
        last: tuple[str, str] | None = None
        while not self._stop.is_set():
            with self._lock:
                item = self._pending
            if item is None or item == last:
                self._stop.wait(0.5)
                continue
            if self._ipc is None or not self._ipc.connected:
                self._ipc = DiscordIPC(self.client_id)
                if not self._ipc.connect():
                    self._ipc = None
                    self._last_ok = False
                    self._stop.wait(12)
                    continue
            details, state = item
            ok = self._ipc.set_activity(
                details=details,
                state=state,
                timestamps={"start": self._start_ts},
            )
            self._last_ok = ok
            if ok:
                last = item
            else:
                if self._ipc is not None:
                    self._ipc.close()
                self._ipc = None
            self._stop.wait(0.4)
