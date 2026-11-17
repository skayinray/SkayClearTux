"""Общий слой для всех платформ: запуск команд, права, пути, утилиты.

Здесь нет ничего, что зависело бы от конкретной ОС, кроме определения
семейства системы и способа запросить права администратора.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

# --------------------------------------------------------------------------- #
#  Определение платформы
# --------------------------------------------------------------------------- #
def family() -> str:
    """'linux' | 'macos' | 'windows' | 'other'."""
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    return "other"


FAMILY = family()


def _log():
    """Логгер бэкендов (настраивается в ``skaycleartux.logging_setup``).

    Импорт ленивый, чтобы не создавать цикл между ``common`` и ``logging_setup``.
    """
    from ..logging_setup import get_logger
    return get_logger("backends.common")

# Человекочитаемое имя системы, например «Arch Linux», «macOS 15», «Windows 11»
def os_pretty_name() -> str:
    if FAMILY == "linux":
        try:
            for line in Path("/etc/os-release").read_text(errors="ignore").splitlines():
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass
        return "Linux"
    if FAMILY == "macos":
        return f"macOS {platform.mac_ver()[0] or ''}".strip()
    if FAMILY == "windows":
        return f"Windows {platform.release()}"
    return platform.system() or "Unknown"


def os_short_name() -> str:
    return {"linux": "Linux", "macos": "macOS", "windows": "Windows"}.get(
        FAMILY, platform.system())


# --------------------------------------------------------------------------- #
#  Запуск команд
# --------------------------------------------------------------------------- #
def is_admin() -> bool:
    if FAMILY == "windows":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:  # noqa: BLE001
            return False
    geteuid = getattr(os, "geteuid", None)
    return bool(geteuid is not None and geteuid() == 0)


def _macos_root(cmd: list[str]) -> list[str]:
    """Выполняет команду через osascript с запросом пароля администратора."""
    script = " ".join("'" + str(c).replace("'", "'\\''") + "'" for c in cmd)
    return ["osascript", "-e",
            f'do shell script "{script.replace(chr(34), chr(92) + chr(34))}" '
            "with administrator privileges"]


def _elevate(cmd: list[str]) -> list[str]:
    """Оборачивает команду в запрос прав администратора, если это возможно."""
    if FAMILY == "linux":
        if shutil.which("pkexec"):
            return ["pkexec", *cmd]
        if shutil.which("sudo"):
            return ["sudo", "-n", *cmd]
        return cmd
    if FAMILY == "macos":
        if shutil.which("osascript"):
            return _macos_root(cmd)
        if shutil.which("sudo"):
            return ["sudo", "-n", *cmd]
        return cmd
    # Windows: повышение прав требует отдельного запуска процесса — не
    # оборачиваем, а сообщаем об ошибке на уровне вызывающего кода.
    return cmd


def run(cmd: list[str], root: bool = False, timeout: float | None = None,
        input_text: str | None = None,
        cwd: str | None = None) -> subprocess.CompletedProcess:
    """Запускает команду. Никогда не бросает исключение из-за отсутствия программы."""
    cmd = [str(c) for c in cmd]
    env = {**os.environ, "LC_ALL": "C", "LANG": "C"}
    if root and not is_admin():
        cmd = _elevate(cmd)
    try:
        return subprocess.run(
            cmd, text=True, env=env, cwd=cwd, timeout=timeout,
            input=input_text,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        _log().warning("таймаут команды (%s с): %s", timeout, cmd)
        return subprocess.CompletedProcess(cmd, 127, "", "")
    except (FileNotFoundError, OSError) as e:
        _log().warning("не удалось запустить %s: %s", cmd, e)
        return subprocess.CompletedProcess(cmd, 127, "", "")


def run_out(cmd: list[str], root: bool = False, timeout: float | None = None) -> str:
    """stdout команды без служебного шума sudo/pkexec."""
    r = run(cmd, root=root, timeout=timeout)
    junk = ("sudo:", "incorrect password", "try again", "попробуйте",
            "password", "Sorry, try again")
    lines = [ln for ln in (r.stdout or "").splitlines()
             if not any(j in ln.lower() for j in junk)]
    return "\n".join(lines).strip()


def which(name: str) -> str | None:
    return shutil.which(name)


def read_text(path: str | Path) -> str:
    try:
        return Path(path).read_text(errors="ignore").strip()
    except OSError:
        return ""


def write_text(path: str | Path, text: str) -> bool:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------- #
#  Пути приложения (заметки, настройки, отчёты)
# --------------------------------------------------------------------------- #
def app_data_dir() -> Path:
    if FAMILY == "windows":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "SkayClearTux"
    if FAMILY == "macos":
        return Path.home() / "Library" / "Application Support" / "SkayClearTux"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "SkayClearTux"


def downloads_dir() -> Path:
    for name in ("Downloads", "Загрузки"):
        p = Path.home() / name
        if p.is_dir():
            return p
    return Path.home()


# --------------------------------------------------------------------------- #
#  Размеры
# --------------------------------------------------------------------------- #
def human(n: float) -> str:
    n = float(n)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if abs(n) < 1024.0:
            return f"{int(n)} Б" if unit == "Б" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} ПБ"


def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        try:
            return path.lstat().st_size
        except OSError:
            return 0
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


# --------------------------------------------------------------------------- #
#  Чистые утилиты (одинаковы на всех ОС)
# --------------------------------------------------------------------------- #
ALGOS = ("md5", "sha1", "sha256", "sha512")


def hash_text(text: str, algo: str = "sha256") -> str:
    return hashlib.new(algo, text.encode()).hexdigest()


def hash_file(path: str, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_hash(path: str, expected: str, algo: str = "sha256") -> bool:
    return hash_file(path, algo).lower() == expected.strip().lower()


def text_transform(mode: str, text: str) -> str:
    try:
        if mode == "base64e":
            return base64.b64encode(text.encode()).decode()
        if mode == "base64d":
            return base64.b64decode(text.encode()).decode(errors="replace")
        if mode == "urle":
            return urllib.parse.quote(text, safe="")
        if mode == "urld":
            return urllib.parse.unquote(text)
        if mode == "json":
            return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        if mode == "jsonmin":
            return json.dumps(json.loads(text), ensure_ascii=False,
                              separators=(",", ":"))
        if mode == "upper":
            return text.upper()
        if mode == "lower":
            return text.lower()
        if mode == "reverse":
            return text[::-1]
        if mode == "strip":
            return "\n".join(ln.strip() for ln in text.splitlines())
        if mode == "sort":
            return "\n".join(sorted(text.splitlines()))
        if mode == "count":
            return (f"Символов: {len(text)}\nСлов: {len(text.split())}\n"
                    f"Строк: {len(text.splitlines())}")
    except Exception as e:  # noqa: BLE001
        return f"Ошибка: {e}"
    return text


def copy_tree(src: str, dst: str, delete: bool = False) -> tuple[bool, str]:
    """Резервное копирование без внешних зависимостей (rsync не нужен)."""
    s, d = Path(src).expanduser(), Path(dst).expanduser()
    if not s.exists():
        return False, f"источник не найден: {s}"
    try:
        if s.is_file():
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
            return True, f"скопирован файл {s.name}"
        shutil.copytree(s, d, dirs_exist_ok=True)
        removed = 0
        if delete:
            for existing in d.iterdir():
                if not (s / existing.name).exists():
                    if existing.is_dir():
                        shutil.rmtree(existing, ignore_errors=True)
                    else:
                        existing.unlink(missing_ok=True)
                    removed += 1
        msg = f"скопировано: {s} → {d}"
        if delete:
            msg += f" (удалено лишнего: {removed})"
        return True, msg
    except OSError as e:
        return False, f"ошибка копирования: {e}"
