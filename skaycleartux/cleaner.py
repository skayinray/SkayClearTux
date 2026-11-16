"""Движок очистки системы SkayClearTux.

Сканирование — только чтение. Чистка привилегированных категорий идёт через
системный запрос пароля (pkexec/sudo на Linux, osascript на macOS, UAC на
Windows) — см. common.run(root=True).

Категории мусора подбираются под текущую ОС: Linux — pacman/systemd, macOS —
Homebrew/LaunchServices, Windows — временные файлы и кэши браузеров.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .backends import common

HOME = Path.home()
FAMILY = common.FAMILY
CACHE = HOME / ".cache"

run = common.run
out = common.run_out
human = common.human


def du_bytes(path: Path) -> int:
    return common.dir_size(path)


def clear_contents(path: Path) -> int:
    if not path.is_dir():
        return 0
    freed = du_bytes(path)
    for entry in os.listdir(path):
        fp = path / entry
        try:
            if fp.is_dir() and not fp.is_symlink():
                shutil.rmtree(fp, ignore_errors=True)
            else:
                fp.unlink(missing_ok=True)
        except OSError:
            pass
    return freed


# --------------------------------------------------------------------------- #
@dataclass
class Category:
    key: str
    title: str
    desc: str
    risk: str                       # low | medium | high
    needs_root: bool = False
    scan: object = None
    clean: object = None
    size: int = 0
    detail: str = ""

    @property
    def risk_ru(self) -> str:
        return {"low": "безопасно", "medium": "внимание", "high": "опасно"}[self.risk]

    @property
    def safe(self) -> bool:
        return self.risk == "low"


def _scan_dir(p: Path):
    def f():
        b = du_bytes(p)
        return b, (f"каталог {p}" if b else "пусто")
    return f


def _clean_dir(p: Path):
    def f():
        return clear_contents(p), f"очищено: {p}"
    return f


# =========================================================================== #
#  Linux
# =========================================================================== #
def _linux_categories() -> list[Category]:
    def scan_pacman():
        p = Path("/var/cache/pacman/pkg")
        n = len(list(p.glob("*.pkg.tar.*"))) if p.is_dir() else 0
        return du_bytes(p), f"{n} файлов пакетов"

    def clean_pacman():
        before = du_bytes(Path("/var/cache/pacman/pkg"))
        run(["paccache", "-rk1"], root=True)
        return max(0, before - du_bytes(Path("/var/cache/pacman/pkg"))), \
            "paccache -rk1 (оставлена 1 версия)"

    def scan_journal():
        s = out(["journalctl", "--disk-usage"])
        num = 0.0
        for tok in s.replace(",", ".").split():
            t = tok.rstrip(".")
            if t and t[-1] in "KMG" and t[:-1].replace(".", "", 1).isdigit():
                num = float(t[:-1]) * {"K": 1e3, "M": 1e6, "G": 1e9}[t[-1]]
                break
        if num == 0.0:
            num = float(du_bytes(Path("/var/log/journal")))
        return int(num), (s or "журнал systemd")

    def clean_journal():
        before = scan_journal()[0]
        run(["journalctl", "--vacuum-size=150M"], root=True)
        return max(0, before - scan_journal()[0]), "vacuum до 150 МБ"

    def scan_orphans():
        pkgs = [p for p in out(["pacman", "-Qdtq"]).split("\n") if p]
        total = 0
        for p in pkgs:
            for line in out(["pacman", "-Qi", p]).splitlines():
                if line.startswith("Installed Size"):
                    part = line.split(":", 1)[1].strip().split()
                    if len(part) == 2:
                        total += int(float(part[0]) * {
                            "b": 1, "kib": 1024, "mib": 1024 ** 2,
                            "gib": 1024 ** 3}.get(part[1].lower(), 0))
        return total, (", ".join(pkgs) if pkgs else "нет сирот")

    def clean_orphans():
        pkgs = [p for p in out(["pacman", "-Qdtq"]).split("\n") if p]
        if not pkgs:
            return 0, "сирот нет"
        before = scan_orphans()[0]
        run(["pacman", "-Rns", "--noconfirm", *pkgs], root=True)
        return before, f"удалено {len(pkgs)} пакетов"

    def scan_flatpak():
        if not shutil.which("flatpak"):
            return 0, "flatpak не установлен"
        r = out(["flatpak", "uninstall", "--unused", "--dry-run"])
        return 0, ("есть неиспользуемые runtime" if r and "Nothing" not in r
                   else "неиспользуемых нет")

    def clean_flatpak():
        if not shutil.which("flatpak"):
            return 0, "flatpak не установлен"
        run(["flatpak", "uninstall", "--unused", "-y"])
        return 0, "удалены неиспользуемые runtime"

    def scan_docker():
        if not shutil.which("docker"):
            return 0, "docker не установлен"
        return 0, (out(["docker", "system", "df", "--format",
                        "{{.Reclaimable}}"]).replace("\n", "; ") or "нет данных")

    def clean_docker():
        if not shutil.which("docker"):
            return 0, "docker не установлен"
        run(["docker", "system", "prune", "-af"], root=True)
        return 0, "docker system prune -af"

    def scan_varlog():
        b = 0
        for root, _d, files in os.walk("/var/log"):
            for f in files:
                if f.endswith((".gz", ".1", ".2", ".old", ".xz")) or ".log." in f:
                    try:
                        b += os.lstat(os.path.join(root, f)).st_size
                    except OSError:
                        pass
        return b, "ротированные (старые) логи"

    def clean_varlog():
        freed = 0
        for root, _d, files in os.walk("/var/log"):
            for f in files:
                if f.endswith((".gz", ".1", ".2", ".old", ".xz")) or ".log." in f:
                    fp = os.path.join(root, f)
                    try:
                        freed += os.lstat(fp).st_size
                        run(["rm", "-f", fp], root=True)
                    except OSError:
                        pass
        return freed, "удалены старые логи"

    return [
        Category("pacman-cache", "Кэш пакетов pacman",
                 "Скачанные пакеты. Оставляем 1 последнюю версию каждого — "
                 "откат возможен.", "low", needs_root=True,
                 scan=scan_pacman, clean=clean_pacman),
        Category("journal", "Журнал systemd", "Ужимаем до 150 МБ. Свежие логи остаются.",
                 "low", needs_root=True, scan=scan_journal, clean=clean_journal),
        Category("yay-cache", "Кэш сборки yay",
                 "Исходники и пакеты AUR-сборок. Пересоберутся при следующем обновлении.",
                 "low", scan=_scan_dir(CACHE / "yay"), clean=_clean_dir(CACHE / "yay")),
        Category("browser-cache", "Кэш браузеров", "Firefox/Chromium. Пересоздаётся сам.",
                 "low", scan=_scan_dir(CACHE / "mozilla"),
                 clean=_clean_dir(CACHE / "mozilla")),
        Category("thumbnails", "Миниатюры", "Превью файлов. Пересоздаются.",
                 "low", scan=_scan_dir(CACHE / "thumbnails"),
                 clean=_clean_dir(CACHE / "thumbnails")),
        Category("mesa-shader", "Кэш шейдеров Mesa",
                 "Кэш шейдеров GPU. Пересоздаётся (первый запуск игр чуть дольше).",
                 "low", scan=_scan_dir(CACHE / "mesa_shader_cache"),
                 clean=_clean_dir(CACHE / "mesa_shader_cache")),
        Category("wine-cache", "Кэш Wine", "Кэш Wine/Proton. Безопасно.",
                 "low", scan=_scan_dir(CACHE / "wine"), clean=_clean_dir(CACHE / "wine")),
        Category("flatpak-unused", "Неиспользуемые Flatpak",
                 "Устаревшие runtime Flatpak, не нужные приложениям.",
                 "low", scan=scan_flatpak, clean=clean_flatpak),
        Category("docker", "Docker/Podman мусор",
                 "Остановленные контейнеры, неиспользуемые образы и тома.",
                 "low", needs_root=True, scan=scan_docker, clean=clean_docker),
        Category("var-log", "Старые системные логи",
                 "Ротированные логи в /var/log (*.gz, *.1 и т.п.).",
                 "low", needs_root=True, scan=scan_varlog, clean=clean_varlog),
        Category("huggingface", "Кэш моделей HuggingFace",
                 "Скачанные ML-модели. Удаление = повторная загрузка.",
                 "medium", scan=_scan_dir(CACHE / "huggingface"),
                 clean=_clean_dir(CACHE / "huggingface")),
        Category("whisper", "Кэш моделей Whisper",
                 "Модели распознавания речи. Удаление = повторная загрузка.",
                 "medium", scan=_scan_dir(CACHE / "whisper"),
                 clean=_clean_dir(CACHE / "whisper")),
        Category("trash", "Корзина",
                 "Файлы, которые ты сам отправил в корзину. Восстановить не получится!",
                 "medium", scan=_scan_trash, clean=_clean_trash),
        Category("orphans", "Пакеты-сироты",
                 "Установленные как зависимости, но больше никому не нужные.",
                 "medium", needs_root=True, scan=scan_orphans, clean=clean_orphans),
    ]


# =========================================================================== #
#  macOS
# =========================================================================== #
def _macos_categories() -> list[Category]:
    def scan_brew():
        if not shutil.which("brew"):
            return 0, "Homebrew не установлен"
        return du_bytes(HOME / "Library" / "Caches" / "Homebrew"), "кэш Homebrew"

    def clean_brew():
        if not shutil.which("brew"):
            return 0, "Homebrew не установлен"
        before = du_bytes(HOME / "Library" / "Caches" / "Homebrew")
        run(["brew", "cleanup", "-s"])
        return max(0, before - du_bytes(HOME / "Library" / "Caches" / "Homebrew")), \
            "brew cleanup -s"

    return [
        Category("brew-cache", "Кэш Homebrew",
                 "Загруженные бутылки и устаревшие версии. Пересоберутся/скачаются заново.",
                 "low", scan=scan_brew, clean=clean_brew),
        Category("user-caches", "Кэш приложений (~/Library/Caches)",
                 "Кэши приложений. Пересоздаются автоматически.",
                 "low", scan=_scan_dir(HOME / "Library" / "Caches"),
                 clean=_clean_dir(HOME / "Library" / "Caches")),
        Category("logs", "Логи пользователя",
                 "Старые журналы в ~/Library/Logs.", "low",
                 scan=_scan_dir(HOME / "Library" / "Logs"),
                 clean=_clean_dir(HOME / "Library" / "Logs")),
        Category("xcode", "Xcode DerivedData",
                 "Промежуточные сборки Xcode. Соберутся заново при следующей сборке.",
                 "medium", scan=_scan_dir(HOME / "Library" / "Developer" /
                                          "Xcode" / "DerivedData"),
                 clean=_clean_dir(HOME / "Library" / "Developer" / "Xcode" /
                                  "DerivedData")),
        Category("trash", "Корзина",
                 "Файлы из корзины. Восстановить не получится!", "medium",
                 scan=_scan_trash, clean=_clean_trash),
    ]


# =========================================================================== #
#  Windows
# =========================================================================== #
def _windows_categories() -> list[Category]:
    local = Path(os.environ.get("LOCALAPPDATA", str(HOME / "AppData" / "Local")))
    roaming = Path(os.environ.get("APPDATA", str(HOME / "AppData" / "Roaming")))
    temp = Path(os.environ.get("TEMP", str(local / "Temp")))

    def scan_temp():
        return du_bytes(temp), "временные файлы пользователя"

    def clean_temp():
        freed = 0
        for entry in list(temp.glob("*")):
            try:
                if entry.is_dir() and not entry.is_symlink():
                    freed += du_bytes(entry)
                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    freed += entry.stat().st_size
                    entry.unlink(missing_ok=True)
            except OSError:
                pass
        return freed, "очищены временные файлы"

    def scan_recycle():
        try:
            r = out(["powershell", "-NoProfile", "-Command",
                     "(New-Object -ComObject Shell.Application).NameSpace(10)."
                     "Items() | Measure-Object -Property Size -Sum | "
                     "Select-Object -ExpandProperty Sum"])
            return int(float(r or 0)), "корзина Windows"
        except (ValueError, TypeError):
            return 0, "корзина Windows"

    def clean_recycle():
        before = scan_recycle()[0]
        run(["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force"])
        return before, "корзина очищена"

    return [
        Category("temp", "Временные файлы (%TEMP%)",
                 "Временные файлы программ. Удаляются безопасно.", "low",
                 scan=scan_temp, clean=clean_temp),
        Category("browser-cache", "Кэш браузеров (Chrome/Edge)",
                 "Кэш Chromium-браузеров. Пересоздаётся сам.", "low",
                 scan=_scan_dir(local / "Google" / "Chrome" / "User Data" /
                                "Default" / "Cache"),
                 clean=_clean_dir(local / "Google" / "Chrome" / "User Data" /
                                  "Default" / "Cache")),
        Category("thumbnails", "Кэш эскизов",
                 "Эскизы Проводника. Пересоздаются.", "low",
                 scan=_scan_dir(local / "Microsoft" / "Windows" / "Explorer"),
                 clean=_clean_dir(local / "Microsoft" / "Windows" / "Explorer")),
        Category("crashdumps", "Дампы и отчёты о сбоях",
                 "Отчёты Windows Error Reporting.", "low",
                 scan=_scan_dir(local / "Microsoft" / "Windows" / "WER"),
                 clean=_clean_dir(local / "Microsoft" / "Windows" / "WER")),
        Category("packages-cache", "Кэш установщиков",
                 "Скачанные пакеты приложений (например, winget).", "medium",
                 scan=_scan_dir(local / "Packages" / "Microsoft.DesktopAppInstaller"
                                / "LocalState"),
                 clean=_clean_dir(local / "Packages" /
                                  "Microsoft.DesktopAppInstaller" / "LocalState")),
        Category("trash", "Корзина",
                 "Файлы из корзины. Восстановить не получится!", "medium",
                 scan=scan_recycle, clean=clean_recycle),
    ]


# =========================================================================== #
#  Общая корзина (Linux/macOS)
# =========================================================================== #
def _trash_dirs() -> list[Path]:
    if FAMILY == "macos":
        return [HOME / ".Trash"]
    return [HOME / ".local" / "share" / "Trash"]


def _scan_trash():
    b = 0
    for d in _trash_dirs():
        b += du_bytes(d / "files") if (d / "files").exists() else du_bytes(d)
    return b, "корзина"


def _clean_trash():
    freed = 0
    for d in _trash_dirs():
        if (d / "files").exists():
            for sub in ("files", "info", "expunged"):
                if (d / sub).exists():
                    freed += clear_contents(d / sub)
        else:
            freed += clear_contents(d)
    return freed, "корзина очищена"


# =========================================================================== #
def _build() -> list[Category]:
    if FAMILY == "macos":
        return _macos_categories()
    if FAMILY == "windows":
        return _windows_categories()
    return _linux_categories()


CATEGORIES: list[Category] = _build()
BY_KEY = {c.key: c for c in CATEGORIES}


def scan_all() -> list[Category]:
    for c in CATEGORIES:
        try:
            c.size, c.detail = c.scan()
        except Exception as e:  # noqa: BLE001
            c.size, c.detail = 0, f"ошибка: {e}"
    return CATEGORIES


def disk_free() -> tuple[str, str, int]:
    """(свободно, всего, процент_занято) для корня — кроссплатформенно."""
    try:
        usage = shutil.disk_usage(common.FAMILY == "windows" and
                                  (os.environ.get("SystemDrive", "C:") + "\\") or "/")
        total, free = usage.total, usage.free
        percent = int((total - free) / total * 100) if total else 0
        return human(free), human(total), percent
    except (OSError, ValueError):
        return "?", "?", 0
