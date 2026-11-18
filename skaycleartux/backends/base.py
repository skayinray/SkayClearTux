"""Базовый интерфейс системного бэкенда.

Каждая платформа (Linux / macOS / Windows) переопределяет методы, которые
умеет. Всё непереопределённое возвращает безопасную заглушку, поэтому
программа никогда не падает из-за отсутствующей функции на конкретной ОС.
"""
from __future__ import annotations

import os

from . import common

NOT_AVAILABLE = "На этой системе функция недоступна."


class BaseBackend:
    name = "base"
    display = "Неизвестная система"

    # ------------------------------------------------------------ процессы
    def list_processes(self) -> list[dict]:
        return []

    def kill_process(self, pid: int, force: bool = False) -> tuple[bool, str]:
        return False, NOT_AVAILABLE

    # --------------------------------------------------------------- службы
    def list_services(self) -> list[dict]:
        return []

    def service_action(self, unit: str, action: str) -> tuple[bool, str]:
        return False, NOT_AVAILABLE

    # --------------------------------------------------------------- пакеты
    def package_manager(self) -> str:
        return ""

    def search_packages(self, query: str) -> list[dict]:
        return []

    def install_packages(self, names: list[str]) -> tuple[bool, str]:
        return False, NOT_AVAILABLE

    def remove_packages(self, names: list[str]) -> tuple[bool, str]:
        return False, NOT_AVAILABLE

    def package_files(self, pkg: str) -> str:
        return NOT_AVAILABLE

    def file_owner(self, path: str) -> str:
        return NOT_AVAILABLE

    def package_info(self, pkg: str) -> str:
        return NOT_AVAILABLE

    # ----------------------------------------------------------- обновления
    def check_updates(self) -> list[dict]:
        return []

    def system_update(self) -> tuple[bool, str]:
        return False, NOT_AVAILABLE

    # ----------------------------------------------------------------- сеть
    def network_info(self) -> dict:
        return {"hostname": common.os_pretty_name(), "interfaces": [],
                "route": "", "dns": []}

    def ping_test(self, host: str = "1.1.1.1", count: int = 4) -> dict:
        flag = "-n" if common.FAMILY == "windows" else "-c"
        r = common.run(["ping", flag, str(count), host], timeout=count + 6)
        raw = r.stdout or ""
        loss = next((ln.strip() for ln in raw.splitlines()
                     if "loss" in ln.lower() or "потер" in ln.lower()), "")
        avg = next((ln.strip() for ln in raw.splitlines()
                    if "avg" in ln.lower() or "средн" in ln.lower()), "")
        return {"raw": raw, "loss": loss, "avg": avg, "ok": r.returncode == 0}

    def public_ip(self) -> str:
        for url in ("https://api.ipify.org", "https://ifconfig.me/ip",
                    "https://icanhazip.com"):
            r = common.run(["curl", "-s", "-m", "6", url], timeout=8)
            ip = (r.stdout or "").strip()
            if ip and len(ip) < 46 and " " not in ip:
                return ip
        return ""

    # -------------------------------------------------------------- датчики
    def sensors_info(self) -> tuple[list, list]:
        return [], []

    def memory_info(self) -> tuple[float, float]:
        return 0.0, 0.0

    def load_avg(self) -> tuple[float, float, float]:
        try:
            return tuple(os.getloadavg())  # type: ignore[return-value]
        except Exception:  # noqa: BLE001
            return 0.0, 0.0, 0.0

    def cpu_percent(self) -> float:
        return 0.0

    def uptime(self) -> str:
        return "—"

    def cpu_model(self) -> str:
        import platform
        return platform.processor() or "CPU"

    def battery_info(self) -> dict | None:
        return None

    # ------------------------------------------------------------- автозапуск
    def list_startup(self) -> list[dict]:
        return []

    def set_startup_enabled(self, entry: dict, enabled: bool) -> bool:
        return False

    # ------------------------------------------------------------------ диск
    def disk_usage(self, path: str | None = None) -> tuple[int, int, int]:
        import shutil
        try:
            usage = shutil.disk_usage(path or self.root_path())
            total, free = usage.total, usage.free
            percent = int((total - free) / total * 100) if total else 0
            return total, free, percent
        except (OSError, ValueError):
            return 0, 0, 0

    def root_path(self) -> str:
        return "/"

    def mounts(self) -> list[dict]:
        return []

    def disks_overview(self) -> str:
        return NOT_AVAILABLE

    def smart_health(self) -> str:
        return NOT_AVAILABLE

    # ----------------------------------------------------------- железо и пр.
    def hardware_sections(self) -> list[tuple[str, str]]:
        return []

    def diagnostics(self) -> list[tuple[str, str]]:
        return []

    def boot_analysis(self) -> list[tuple[str, str]]:
        return [("Анализ загрузки", NOT_AVAILABLE)]

    def list_timers_raw(self) -> str:
        return NOT_AVAILABLE

    def list_modules(self) -> list[dict]:
        return []

    def module_action(self, name: str, action: str) -> tuple[bool, str]:
        return False, NOT_AVAILABLE

    def firewall_status(self) -> str:
        return NOT_AVAILABLE

    def firewall_status_root(self) -> str:
        return NOT_AVAILABLE

    def journal_entries(self, priority: str = "err", lines: int = 200,
                        unit: str = "") -> str:
        return NOT_AVAILABLE

    # ----------------------------------------------------------------- порты
    def listening_ports(self) -> list[dict]:
        return []

    def established_connections(self) -> list[dict]:
        return []

    # ----------------------------------------------------------------- твики
    def get_swappiness(self) -> int:
        return 60

    def set_swappiness(self, value: int) -> bool:
        return False

    def cpu_governor(self) -> str:
        return "—"

    def cpu_governors(self) -> list[str]:
        return []

    def set_cpu_governor(self, governor: str) -> bool:
        return False

    def thp_status(self) -> str:
        return "—"

    def zram_status(self) -> str:
        return "—"

    # --------------------------------------------------------------- корзина
    def trash_items(self) -> list[dict]:
        return []

    def empty_trash(self) -> tuple[bool, str]:
        return False, NOT_AVAILABLE

    # ----------------------------------------------------------- оптимизация памяти
    def memory_details(self) -> dict:
        """Расширенная информация о памяти (ГБ)."""
        total, used = self.memory_info()
        total = float(total or 0.0)
        used = float(used or 0.0)
        avail = max(0.0, total - used)
        percent = (used / total * 100.0) if total > 0 else 0.0
        return {
            "total_gb": total,
            "used_gb": used,
            "available_gb": avail,
            "percent": percent,
            "swap_total_gb": 0.0,
            "swap_used_gb": 0.0,
            "cached_gb": 0.0,
            "buffers_gb": 0.0,
            "note": "",
        }

    def optimize_memory(self) -> tuple[bool, str]:
        """Попытка безопасно освободить часть памяти/кэшей."""
        return False, NOT_AVAILABLE

    # ------------------------------------------------------------- большой файл
    def large_files(self, root, min_mb: int = 100, limit: int = 300) -> list:
        import os
        min_bytes = min_mb * 1024 * 1024
        results: list[tuple[str, int]] = []
        skip = {".git", "node_modules", ".cache", "Library", "AppData"}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for name in filenames:
                path = os.path.join(dirpath, name)
                try:
                    size = os.lstat(path).st_size
                except OSError:
                    continue
                if size >= min_bytes:
                    results.append((path, size))
        results.sort(key=lambda item: item[1], reverse=True)
        return results[:limit]
