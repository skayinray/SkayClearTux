"""Системные инструменты SkayClearTux.

Это тонкий фасад над платформенными бэкендами (`skaycleartux.backends`).
Конкретную реализацию выбирает сам бэкенд по текущей ОС, поэтому один и тот
же код работает на Linux, macOS и Windows, а недоступные функции аккуратно
сообщают об этом вместо падения.

Все операции чтения выполняются без прав администратора. Привилегированные
действия запрашивают пароль средствами ОС (pkexec/sudo — Linux, osascript —
macOS, UAC — Windows).
"""
from __future__ import annotations

from pathlib import Path

from .backends import common, get_backend
from .backends.common import (ALGOS, dir_size, hash_file, hash_text, human,
                              text_transform, verify_hash)

BACKEND = get_backend()

# для совместимости со старым кодом
run = common.run
out = common.run_out


def backend():
    return BACKEND


def platform_name() -> str:
    return common.os_short_name()


def os_pretty_name() -> str:
    return common.os_pretty_name()


# =========================================================================== #
#  Процессы
# =========================================================================== #
def list_processes() -> list[dict]:
    return BACKEND.list_processes()


def kill_process(pid: int, force: bool = False) -> tuple[bool, str]:
    return BACKEND.kill_process(pid, force)


# =========================================================================== #
#  Службы
# =========================================================================== #
def list_services() -> list[dict]:
    return BACKEND.list_services()


def service_action(unit: str, action: str) -> tuple[bool, str]:
    return BACKEND.service_action(unit, action)


# =========================================================================== #
#  Пакеты
# =========================================================================== #
def package_manager() -> str:
    return BACKEND.package_manager()


def search_packages(query: str) -> list[dict]:
    return BACKEND.search_packages(query)


def install_packages(names: list[str]) -> tuple[bool, str]:
    return BACKEND.install_packages(names)


def remove_packages(names: list[str]) -> tuple[bool, str]:
    return BACKEND.remove_packages(names)


def package_files(pkg: str) -> str:
    return BACKEND.package_files(pkg)


def file_owner(path: str) -> str:
    return BACKEND.file_owner(path)


def package_info(pkg: str) -> str:
    return BACKEND.package_info(pkg)


# старые имена (используются на странице «Пакеты»)
pacman_search = search_packages
pacman_install = install_packages
pacman_remove = remove_packages
pacman_installed = lambda: {p["name"] for p in search_packages("")}  # noqa: E731


# =========================================================================== #
#  Обновления системы
# =========================================================================== #
def check_updates() -> list[dict]:
    return BACKEND.check_updates()


def system_update() -> tuple[bool, str]:
    return BACKEND.system_update()


# =========================================================================== #
#  Сеть
# =========================================================================== #
def network_info() -> dict:
    return BACKEND.network_info()


def ping_test(host: str = "1.1.1.1", count: int = 4) -> dict:
    return BACKEND.ping_test(host, count)


def public_ip() -> str:
    return BACKEND.public_ip()


# =========================================================================== #
#  Датчики и ресурсы
# =========================================================================== #
def sensors_info() -> tuple[list, list]:
    return BACKEND.sensors_info()


def memory_info() -> tuple[float, float]:
    return BACKEND.memory_info()


def load_avg() -> tuple[float, float, float]:
    return BACKEND.load_avg()


def cpu_percent() -> float:
    return BACKEND.cpu_percent()


def cpu_model() -> str:
    return BACKEND.cpu_model()


def uptime() -> str:
    return BACKEND.uptime()


def battery_info() -> dict | None:
    return BACKEND.battery_info()


# =========================================================================== #
#  Автозапуск
# =========================================================================== #
def list_startup() -> list[dict]:
    return BACKEND.list_startup()


def set_startup_enabled(entry: dict, enabled: bool) -> bool:
    return BACKEND.set_startup_enabled(entry, enabled)


# =========================================================================== #
#  Диск
# =========================================================================== #
def disk_usage(path: str | None = None) -> tuple[int, int, int]:
    return BACKEND.disk_usage(path)


def large_files(root: Path, min_mb: int = 100, limit: int = 300) -> list:
    return BACKEND.large_files(root, min_mb, limit)


def mounts() -> list[dict]:
    return BACKEND.mounts()


def disks_overview() -> str:
    return BACKEND.disks_overview()


def smart_health() -> str:
    return BACKEND.smart_health()


def dir_size_str(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return "—"
    return human(dir_size(p))


# =========================================================================== #
#  Железо, диагностика, загрузка, журнал
# =========================================================================== #
def hardware_sections() -> list[tuple[str, str]]:
    return BACKEND.hardware_sections()


def diagnostics() -> list[tuple[str, str]]:
    return BACKEND.diagnostics()


def boot_analysis() -> list[tuple[str, str]]:
    return BACKEND.boot_analysis()


def list_timers_raw() -> str:
    return BACKEND.list_timers_raw()


def journal_entries(priority: str = "err", lines: int = 200, unit: str = "") -> str:
    return BACKEND.journal_entries(priority, lines, unit)


def list_modules() -> list[dict]:
    return BACKEND.list_modules()


def module_action(name: str, action: str) -> tuple[bool, str]:
    return BACKEND.module_action(name, action)


def firewall_status() -> str:
    return BACKEND.firewall_status()


def firewall_status_root() -> str:
    return BACKEND.firewall_status_root()


# =========================================================================== #
#  Порты
# =========================================================================== #
def listening_ports() -> list[dict]:
    return BACKEND.listening_ports()


def established_connections() -> list[dict]:
    return BACKEND.established_connections()


# =========================================================================== #
#  Твики
# =========================================================================== #
def get_swappiness() -> int:
    return BACKEND.get_swappiness()


def set_swappiness(value: int) -> bool:
    return BACKEND.set_swappiness(value)


def cpu_governor() -> str:
    return BACKEND.cpu_governor()


def cpu_governors() -> list[str]:
    return BACKEND.cpu_governors()


def set_cpu_governor(governor: str) -> bool:
    return BACKEND.set_cpu_governor(governor)


def thp_status() -> str:
    return BACKEND.thp_status()


def zram_status() -> str:
    return BACKEND.zram_status()


# =========================================================================== #
#  Заметки
# =========================================================================== #
NOTES_PATH = common.app_data_dir() / "notes.txt"


def load_notes() -> str:
    try:
        return NOTES_PATH.read_text()
    except OSError:
        return ""


def save_notes(text: str) -> bool:
    return common.write_text(NOTES_PATH, text)


# =========================================================================== #
#  Корзина
# =========================================================================== #
def trash_items() -> list[dict]:
    return BACKEND.trash_items()


def empty_trash() -> tuple[bool, str]:
    return BACKEND.empty_trash()


# =========================================================================== #
#  Бэкап
# =========================================================================== #
def run_rsync(src: str, dst: str, delete: bool = False) -> tuple[bool, str]:
    """Копирование папки. Если есть rsync — используем его, иначе встроенное."""
    import shutil
    if shutil.which("rsync"):
        cmd = ["rsync", "-a", "--info=progress2", "--human-readable"]
        if delete:
            cmd.append("--delete")
        cmd += [src, dst]
        r = common.run(cmd)
        return r.returncode == 0, (r.stdout or "").strip()[-6000:] or "готово"
    return common.copy_tree(src, dst, delete)
