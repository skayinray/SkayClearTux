"""Discord Rich Presence для SkayClearTux.

Собственная реализация Discord IPC (Unix-сокет) — без сторонних библиотек.
Активность видна в Discord только пока программа запущена: присутствие привязано
к открытому сокету и исчезает, когда SkayClearTux закрывается.

Application ID берётся из настроек (discord/client_id) — создайте приложение
на https://discord.com/developers/applications и вставьте его ID.
"""
from __future__ import annotations

import json
import os
import socket
import struct
import threading
import time

OP_HANDSHAKE = 0
OP_FRAME = 1
OP_CLOSE = 2
OP_PING = 3
OP_PONG = 4


def _socket_candidates() -> list[str]:
    """Пути к IPC-сокету Discord (обычная установка, Flatpak, Snap, разные индексы)."""
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
    # убрать дубликаты, сохранив порядок
    seen: set[str] = set()
    result: list[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


class DiscordIPC:
    """Минимальный клиент Discord IPC."""

    def __init__(self, client_id: str):
        self.client_id = str(client_id).strip()
        self.sock: socket.socket | None = None

    # ------------------------------------------------------------- транспорт
    def _send(self, op: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        assert self.sock is not None
        self.sock.sendall(struct.pack("<ii", op, len(data)) + data)

    def _read_exact(self, count: int, timeout: float | None) -> bytes | None:
        assert self.sock is not None
        if timeout is not None:
            self.sock.settimeout(timeout)
        buf = b""
        while len(buf) < count:
            try:
                chunk = self.sock.recv(count - len(buf))
            except (socket.timeout, TimeoutError):
                return None
            except OSError:
                return None
            if not chunk:
                return None
            buf += chunk
        return buf

    def _recv(self, timeout: float | None = None):
        header = self._read_exact(8, timeout)
        if header is None:
            return None
        op, length = struct.unpack("<ii", header)
        if length <= 0:
            return op, None
        body = self._read_exact(length, timeout)
        if body is None:
            return None
        try:
            return op, json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return op, None

    # ------------------------------------------------------------------ API
    def connect(self) -> bool:
        if self.sock is not None:
            return True
        if not self.client_id.isdigit():
            return False
        for path in _socket_candidates():
            if not os.path.exists(path):
                continue
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(2.0)
                s.connect(path)
                self.sock = s
                self._send(OP_HANDSHAKE, {"v": 1, "client_id": self.client_id})
                reply = self._recv(2.0)
                if reply is None:
                    raise OSError("нет ответа на рукопожатие")
                self.sock.settimeout(None)
                return True
            except OSError:
                self._safe_close()
        return False

    def set_activity(self, **activity) -> bool:
        if self.sock is None and not self.connect():
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
        if self.sock is None:
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
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    def close(self) -> None:
        self._safe_close()


class DiscordPresence:
    """Фоновый поток, который держит активность Discord в актуальном состоянии."""

    def __init__(self, client_id: str):
        self.client_id = str(client_id).strip()
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
            if self._ipc is None or self._ipc.sock is None:
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
