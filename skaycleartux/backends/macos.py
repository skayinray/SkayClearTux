"""macOS-бэкенд: launchd, Homebrew, ifconfig/scutil, pmset, diskutil.

Всё построено на стандартных утилитах «чистой» macOS. Homebrew используется
только если он найден в PATH (пакеты, обновления, osx-cpu-temp). Там, где
возможность недоступна, методы деградируют корректно и не бросают исключений.
"""
from __future__ import annotations

import datetime
import os
import re
import shutil
import signal
import time
from pathlib import Path

from . import common
from .base import BaseBackend

# Стандартные каталоги launchd-агентов (автозапуск пользователя и системы)
LAUNCH_AGENTS_USER = Path.home() / "Library" / "LaunchAgents"
LAUNCH_AGENTS_SYSTEM = Path("/Library/LaunchAgents")
# Встроенный файрвол macOS (Application Firewall)
SOCKETFILTERFW = "/usr/libexec/ApplicationFirewall/socketfilterfw"


class MacOSBackend(BaseBackend):
    name = "macos"
    display = "macOS"

    # ------------------------------------------------------------ процессы
    def list_processes(self) -> list[dict]:
        # В macOS ps нет --sort, поэтому сортируем сами по загрузке CPU.
        r = common.run(["ps", "-Ao", "pid,user,pcpu,pmem,rss,comm,args"],
                       timeout=15)
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            parts = line.split(None, 6)
            if len(parts) < 7:
                continue
            pid, user, pcpu, pmem, rss, comm, args = parts
            try:
                rows.append({"pid": int(pid), "user": user, "cpu": float(pcpu),
                             "mem": float(pmem), "rss": int(rss),
                             "name": comm, "cmd": args})
            except ValueError:
                continue
        rows.sort(key=lambda item: item["cpu"], reverse=True)
        return rows

    def kill_process(self, pid: int, force: bool = False) -> tuple[bool, str]:
        sig = signal.SIGKILL if force else signal.SIGTERM
        label = "SIGKILL" if force else "SIGTERM"
        try:
            os.kill(pid, sig)
            return True, f"{label} → PID {pid}"
        except ProcessLookupError:
            return False, "процесс уже завершён"
        except PermissionError:
            # Нужны права администратора — просим через osascript (см. common).
            r = common.run(["kill", "-9" if force else "-15", str(pid)],
                           root=True)
            ok = r.returncode == 0
            return ok, (f"{label} через администратора → PID {pid}" if ok
                        else "нужны права администратора")
        except OSError as e:  # noqa: BLE001
            return False, f"ошибка: {e}"

    # --------------------------------------------------------------- службы
    def list_services(self) -> list[dict]:
        # launchctl list печатает «PID\tStatus\tLabel»; PID == "-" → не запущен.
        r = common.run(["launchctl", "list"], timeout=15)
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            pid, status, label = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if pid == "PID" or not label:
                continue
            rows.append({"unit": label, "load": "launchd",
                         "active": "running" if pid not in ("-", "") else "loaded",
                         "sub": status, "desc": ""})
        return rows

    def service_action(self, unit: str, action: str) -> tuple[bool, str]:
        if not unit or not unit.strip():
            return False, "Укажи имя службы"
        label = unit.strip()
        if action in ("start", "restart"):
            sub = ["kickstart", "-k"]
            verb = "запущена" if action == "start" else "перезапущена"
        elif action == "stop":
            sub, verb = ["kill", "SIGTERM"], "остановлена"
        elif action == "enable":
            sub, verb = ["enable"], "включена"
        elif action == "disable":
            sub, verb = ["disable"], "отключена"
        else:
            return False, f"Действие «{action}» не поддерживается в launchd"
        # Полное имя цели в launchd включает домен; пробуем как есть и system/<label>.
        targets = [label]
        if not label.startswith(("system/", "gui/", "user/")):
            targets.append(f"system/{label}")
        for target in targets:
            r = common.run(["launchctl", *sub, target], root=True, timeout=20)
            if r.returncode == 0:
                return True, f"{label}: служба {verb}"
        return False, (f"{label}: не удалось (проверь точный домен, например "
                       f"system/{label} или gui/$(id -u)/{label})")

    # --------------------------------------------------------------- пакеты
    def package_manager(self) -> str:
        return "brew" if common.which("brew") else ""

    def search_packages(self, query: str) -> list[dict]:
        if not common.which("brew"):
            return []
        r = common.run(["brew", "search", query.strip()], timeout=60)
        installed: set[str] = set()
        ri = common.run(["brew", "list", "--formula"], timeout=60)
        for line in (ri.stdout or "").splitlines():
            line = line.strip()
            if line:
                installed.add(line)
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if not line or line.startswith(("==>", "Error", "Warning")):
                continue
            name = line.split()[0]
            rows.append({"name": name, "version": "", "repo": "homebrew",
                         "installed": name in installed, "desc": ""})
        return rows

    def install_packages(self, names: list[str]) -> tuple[bool, str]:
        names = [n for n in names if n.strip()]
        if not names:
            return False, "Не указаны пакеты"
        if not common.which("brew"):
            return False, "Homebrew не установлен (см. https://brew.sh)"
        r = common.run(["brew", "install", *names], timeout=3600)
        return r.returncode == 0, (r.stdout or "").strip()[-4000:]

    def remove_packages(self, names: list[str]) -> tuple[bool, str]:
        names = [n for n in names if n.strip()]
        if not names:
            return False, "Не указаны пакеты"
        if not common.which("brew"):
            return False, "Homebrew не установлен (см. https://brew.sh)"
        r = common.run(["brew", "uninstall", *names], timeout=1800)
        return r.returncode == 0, (r.stdout or "").strip()[-4000:]

    def package_files(self, pkg: str) -> str:
        if not pkg.strip():
            return "Укажи имя пакета"
        if not common.which("brew"):
            return "Homebrew не установлен"
        return common.run_out(["brew", "list", pkg.strip()], timeout=30) or \
            "Пакет не найден или не установлен"

    def file_owner(self, path: str) -> str:
        if not path.strip():
            return "Укажи путь к файлу"
        target = path.strip()
        # pkgutil знает о файлах, установленных пакетами .pkg
        out = common.run_out(["pkgutil", "--file-info", target], timeout=15)
        if out:
            return out
        # Homebrew хранит связь «файл → формула»
        if common.which("brew"):
            owner = common.run_out(["brew", "which-formula", "--", target],
                                   timeout=20)
            if owner:
                return f"Homebrew: {owner}"
        return "Владелец не определён (файл не из .pkg/Homebrew)"

    def package_info(self, pkg: str) -> str:
        if not pkg.strip():
            return "Укажи имя пакета"
        if not common.which("brew"):
            return "Homebrew не установлен"
        return common.run_out(["brew", "info", pkg.strip()], timeout=30) or \
            "Пакет не найден"

    # ----------------------------------------------------------- обновления
    def check_updates(self) -> list[dict]:
        if not common.which("brew"):
            return []
        r = common.run(["brew", "outdated"], timeout=120)
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if not line or line.startswith(("==>", "Error", "Warning")):
                continue
            # Формат: "имя (старая_версия) < новая_версия"
            m = re.match(r"^(\S+)\s+\(([^)]+)\)\s*(?:<|!=)\s*(\S+)", line)
            if m:
                rows.append({"name": m.group(1), "old": m.group(2),
                             "new": m.group(3)})
            else:
                parts = line.split()
                if parts:
                    rows.append({"name": parts[0], "old": "",
                                 "new": parts[-1]})
        return rows

    def system_update(self) -> tuple[bool, str]:
        if not common.which("brew"):
            return False, "Homebrew не установлен (обновление системы — в «Обновлении ПО»)"
        r = common.run(["brew", "upgrade"], timeout=7200)
        return r.returncode == 0, (r.stdout or "").strip()[-6000:]

    # ----------------------------------------------------------------- сеть
    def network_info(self) -> dict:
        try:
            hostname = os.uname().nodename
        except (AttributeError, OSError):
            hostname = common.os_pretty_name()
        info: dict = {"hostname": hostname, "interfaces": [], "route": "",
                      "dns": []}
        # Интерфейсы, адреса и MAC-адреса из ifconfig
        r = common.run(["ifconfig", "-a"], timeout=15)
        cur: dict | None = None
        for line in (r.stdout or "").splitlines():
            if line and not line[0].isspace() and ":" in line:
                name = line.split(":", 1)[0]
                m = re.search(r"<([^>]*)>", line)
                flags = m.group(1).split(",") if m else []
                cur = {"name": name, "state": "UP" if "UP" in flags else "DOWN",
                       "addrs": [], "mac": ""}
                info["interfaces"].append(cur)
            elif cur is not None:
                s = line.strip()
                if s.startswith("inet "):
                    cur["addrs"].append(s.split()[1])
                elif s.startswith("inet6 "):
                    cur["addrs"].append(s.split()[1])
                elif s.startswith("ether "):
                    cur["mac"] = s.split()[1]
        # Маршрут по умолчанию
        info["route"] = self._default_route()
        # DNS через scutil
        dns_text = common.run_out(["scutil", "--dns"], timeout=10)
        for line in dns_text.splitlines():
            s = line.strip()
            if s.startswith("nameserver["):
                _, _, ip = s.partition(":")
                ip = ip.strip()
                if ip and ip not in info["dns"]:
                    info["dns"].append(ip)
        return info

    @staticmethod
    def _default_route() -> str:
        text = common.run_out(["route", "-n", "get", "default"], timeout=10)
        gw = dev = ""
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("gateway:"):
                gw = s.split(":", 1)[1].strip()
            elif s.startswith("interface:"):
                dev = s.split(":", 1)[1].strip()
        if gw or dev:
            return f"default via {gw} dev {dev}".strip()
        # Запасной вариант — таблица маршрутов
        for line in common.run_out(["netstat", "-rn"], timeout=10).splitlines():
            if line.startswith("default"):
                return " ".join(line.split())
        return ""

    # -------------------------------------------------------------- датчики
    def sensors_info(self) -> tuple[list, list]:
        temps: list[tuple[str, float]] = []
        fans: list[tuple[str, float]] = []
        # osx-cpu-temp (Homebrew) — самый простой источник температуры
        tool = common.which("osx-cpu-temp")
        if tool:
            out = common.run_out([tool], timeout=10)
            m = re.search(r"(-?[\d.]+)", out)
            if m:
                try:
                    temps.append(("CPU", float(m.group(1))))
                except ValueError:
                    pass
        # Иначе — уровень тепловой защиты XCPM (не температура, но индикатор)
        if not temps:
            raw = common.run_out(["sysctl", "-n", "machdep.xcpm.cpu_thermal_level"],
                                 timeout=10)
            if raw:
                try:
                    temps.append(("CPU thermal level", float(raw)))
                except ValueError:
                    pass
        # Вентиляторы через ioreg (best-effort, ключи вида F0Ac)
        try:
            out = common.run_out(["ioreg", "-c", "AppleSMC", "-r", "-d", "1"],
                                 timeout=10)
            for m in re.finditer(r'"F(\d+)Ac"\s*=\s*(\d+)', out):
                fans.append((f"Вентилятор {m.group(1)}", float(m.group(2))))
        except Exception:  # noqa: BLE001
            pass
        return temps, fans

    def _vm_stat(self) -> tuple[float, dict[str, int], int]:
        try:
            total = int(common.run_out(["sysctl", "-n", "hw.memsize"],
                                       timeout=10)) / (1024 ** 3)
        except (TypeError, ValueError):
            return 0.0, {}, 4096
        text = (common.run(["vm_stat"], timeout=10).stdout) or ""
        page_size = 4096
        m = re.search(r"page size of (\d+) bytes", text)
        if m:
            page_size = int(m.group(1))
        vals: dict[str, int] = {}
        for label in ("Pages free", "Pages inactive", "Pages speculative",
                      "File-backed pages", "Pages wired down", "Pages active"):
            mm = re.search(rf"{label}:\s+(\d+)", text)
            vals[label] = int(mm.group(1)) if mm else 0
        return total, vals, page_size

    def memory_info(self) -> tuple[float, float]:
        total, vals, page_size = self._vm_stat()
        if total <= 0:
            return 0.0, 0.0
        avail = (vals.get("Pages free", 0) + vals.get("Pages inactive", 0)) * page_size
        avail_gb = avail / (1024 ** 3)
        return total, max(0.0, total - avail_gb)

    def memory_details(self) -> dict:
        total, used = self.memory_info()
        swap_total = swap_used = 0.0
        sw = common.run_out(["sysctl", "-n", "vm.swapusage"], timeout=10)
        # пример: total = 2048.00M  used = 512.00M  free = 1536.00M
        mt = re.search(r"total = ([\d.]+)M", sw)
        mu = re.search(r"used = ([\d.]+)M", sw)
        if mt:
            swap_total = float(mt.group(1)) / 1024.0
        if mu:
            swap_used = float(mu.group(1)) / 1024.0
        _, vals, page_size = self._vm_stat()
        cached = (vals.get("File-backed pages", 0) + vals.get("Pages speculative", 0)
                  ) * page_size / (1024 ** 3)
        return {
            "total_gb": float(total or 0.0),
            "used_gb": float(used or 0.0),
            "available_gb": max(0.0, float(total or 0.0) - float(used or 0.0)),
            "percent": (used / total * 100.0) if total > 0 else 0.0,
            "swap_total_gb": swap_total,
            "swap_used_gb": swap_used,
            "cached_gb": cached,
            "buffers_gb": 0.0,
            "note": "На macOS очистка памяти доступна через команду purge (если установлена).",
        }

    def optimize_memory(self) -> tuple[bool, str]:
        try:
            common.run(["sync"], timeout=15)
        except Exception:  # noqa: BLE001
            pass
        if common.which("purge"):
            r = common.run(["purge"], root=True, timeout=60)
            if r.returncode == 0:
                return True, ("Память оптимизирована командой purge. "
                              "Система может на короткое время замедлиться.")
            return False, ("Не удалось выполнить purge (возможно, нужны права "
                           "администратора или инструменты разработчика).")
        return False, ("Команда purge не найдена. На macOS прямое освобождение "
                       "оперативной памяти ограничено; закройте лишние приложения.")

    def load_avg(self) -> tuple[float, float, float]:
        try:
            a, b, c = os.getloadavg()
            return float(a), float(b), float(c)
        except (AttributeError, OSError):
            return 0.0, 0.0, 0.0

    def cpu_percent(self) -> float:
        # Приблизительно: сумма %CPU по процессам, делённая на число ядер.
        try:
            r = common.run(["ps", "-A", "-o", "%cpu"], timeout=10)
            total = 0.0
            for line in (r.stdout or "").splitlines()[1:]:
                try:
                    total += float(line.strip())
                except ValueError:
                    continue
            cores = os.cpu_count() or 1
            return max(0.0, min(100.0, total / cores))
        except Exception:  # noqa: BLE001
            return 0.0

    def uptime(self) -> str:
        raw = common.run_out(["sysctl", "-n", "kern.boottime"], timeout=5)
        m = re.search(r"sec\s*=\s*(\d+)", raw)
        if not m:
            return "—"
        try:
            secs = max(0.0, time.time() - int(m.group(1)))
        except (TypeError, ValueError):
            return "—"
        h, mnt = divmod(int(secs) // 60, 60)
        d, h = divmod(h, 24)
        return f"{d} д {h} ч {mnt} мин" if d else f"{h} ч {mnt} мин"

    def cpu_model(self) -> str:
        brand = common.run_out(["sysctl", "-n", "machdep.cpu.brand_string"],
                               timeout=5)
        if brand:
            return brand
        import platform
        return platform.processor() or "CPU"

    def battery_info(self) -> dict | None:
        text = (common.run(["pmset", "-g", "batt"], timeout=10).stdout) or ""
        if "%" not in text:
            return None
        m = re.search(r"(\d+)%", text)
        cap = m.group(1) if m else "—"
        low = text.lower()
        if "discharging" in low:
            status = "Discharging"
        elif "charging" in low:
            status = "Charging"
        elif "charged" in low or "ac attached" in low:
            status = "Full"
        else:
            status = "—"
        # Здоровье и ёмкость из ioreg (best-effort)
        health, energy_now, energy_full = "—", "", ""
        try:
            io = common.run_out(["ioreg", "-r", "-c", "AppleSmartBattery"],
                                timeout=10)
            mc = re.search(r'"MaxCapacity"\s*=\s*(\d+)', io)
            dc = re.search(r'"DesignCapacity"\s*=\s*(\d+)', io)
            cc = re.search(r'"CurrentCapacity"\s*=\s*(\d+)', io)
            if mc and dc and int(dc.group(1)):
                health = f"{int(mc.group(1)) * 100 // int(dc.group(1))}%"
            if mc:
                energy_full = mc.group(1)
            if cc:
                energy_now = cc.group(1)
        except Exception:  # noqa: BLE001
            pass
        return {"name": "InternalBattery", "capacity": cap, "status": status,
                "health": health, "energy_now": energy_now,
                "energy_full": energy_full}

    # ------------------------------------------------------------- автозапуск
    def list_startup(self) -> list[dict]:
        rows: list[dict] = []
        for folder, source in ((LAUNCH_AGENTS_USER, "пользователь"),
                               (LAUNCH_AGENTS_SYSTEM, "система")):
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.plist")):
                rows.append({"name": _plist_label(path) or path.stem,
                             "exec": "", "enabled": True, "source": source,
                             "path": path})
        return rows

    def set_startup_enabled(self, entry: dict, enabled: bool) -> bool:
        path = entry.get("path")
        if not path:
            return False
        try:
            target = Path(path)
        except TypeError:
            return False
        # Современный launchd предпочитает bootstrap/bootout, но load/unload
        # остаётся самым совместимым best-effort вариантом.
        action = "load" if enabled else "unload"
        r = common.run(["launchctl", action, str(target)],
                       root=(entry.get("source") == "система"), timeout=15)
        return r.returncode == 0

    # ------------------------------------------------------------------ диск
    def root_path(self) -> str:
        return "/"

    def mounts(self) -> list[dict]:
        rows: list[dict] = []
        r = common.run(["mount"], timeout=10)
        for line in (r.stdout or "").splitlines():
            # Формат: "<src> on <target> (<fstype>, <опции>)"
            m = re.match(r"^(.*?)\s+on\s+(.*?)\s+\(([^,)]+)(?:,\s*(.*))?\)\s*$",
                         line)
            if not m:
                continue
            rows.append({"src": m.group(1), "target": m.group(2),
                         "fstype": m.group(3), "opts": m.group(4) or ""})
        return rows

    def disks_overview(self) -> str:
        dl = common.run_out(["diskutil", "list"], timeout=15)
        df = common.run_out(["df", "-h"], timeout=15)
        return (f"Устройства:\n{dl or '—'}\n\n"
                f"Использование файловых систем:\n{df or '—'}")

    def smart_health(self) -> str:
        devices: list[str] = []
        out = common.run_out(["diskutil", "list"], timeout=15)
        for m in re.finditer(r"(/dev/disk\d+)", out):
            if m.group(1) not in devices:
                devices.append(m.group(1))
        if not devices:
            devices = ["/dev/disk0"]
        parts: list[str] = []
        for dev in devices[:4]:
            info = common.run_out(["diskutil", "info", dev], timeout=15)
            smart = "\n".join(ln.strip() for ln in info.splitlines()
                              if "SMART" in ln)
            parts.append(f"=== {dev} ===\n"
                         f"{smart or 'SMART-данные недоступны'}")
        return "\n\n".join(parts) or "Накопители не найдены"

    # ----------------------------------------------------------- железо и пр.
    def hardware_sections(self) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        hw = common.run_out(["system_profiler", "SPHardwareDataType"],
                            timeout=30)
        if hw:
            sections.append(("Оборудование", hw[:6000]))
        total, used = self.memory_info()
        sections.append(("Память",
                         f"Всего: {total:.1f} ГБ\nИспользовано: {used:.1f} ГБ"))
        return sections

    def diagnostics(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        # Короткий срез ошибок журнала (log show бывает медленным — таймаут).
        errs = common.run_out(["log", "show", "--last", "5m",
                               "--style", "compact",
                               "--predicate", "messageType == error"],
                              timeout=25)
        out.append(("Ошибки в журнале (5 мин)",
                    errs[-4000:] if errs else "нет — всё в порядке"))
        try:
            _total, free, percent = self.disk_usage("/")
            out.append(("Диск /", f"Занято {percent}% "
                                  f"(свободно {common.human(free)})"))
        except Exception:  # noqa: BLE001
            out.append(("Диск /", "нет данных"))
        out.append(("Файрвол", self.firewall_status()))
        # Демоны launchd с ненулевым кодом возврата
        bad: list[str] = []
        for line in common.run_out(["launchctl", "list"], timeout=10).splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) >= 3 and parts[1].strip() not in ("0", "-", ""):
                bad.append(f"{parts[2].strip()} (код {parts[1].strip()})")
        out.append(("Службы с ошибками", "\n".join(bad[:30]) or "нет — всё в порядке"))
        return out

    def boot_analysis(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        raw = common.run_out(["sysctl", "-n", "kern.boottime"], timeout=5)
        m = re.search(r"sec\s*=\s*(\d+)", raw)
        if m:
            try:
                when = datetime.datetime.fromtimestamp(int(m.group(1)))
                out.append(("Загрузка системы",
                            f"Система загружена: {when:%Y-%m-%d %H:%M:%S}"))
            except (ValueError, OSError, OverflowError):
                out.append(("Загрузка системы", f"Система загружена: {raw}"))
        else:
            out.append(("Загрузка системы", "нет данных"))
        items = self.list_startup()
        if items:
            out.append(("Элементы автозапуска",
                        "\n".join(f"{it['name']} ({it['source']})"
                                  for it in items[:40])))
        else:
            out.append(("Элементы автозапуска", "не найдены"))
        return out

    def list_timers_raw(self) -> str:
        return ("В macOS нет отдельного менеджера таймеров: периодические "
                "задачи задаются в launchd-агентах (StartInterval / "
                "StartCalendarInterval в .plist) и в cron.\n"
                "Список заданий launchd: `launchctl list`.")

    def list_modules(self) -> list[dict]:
        # Кext-модули нельзя перечислить так же просто, как lsmod в Linux.
        return []

    def module_action(self, name: str, action: str) -> tuple[bool, str]:
        return False, ("Управление модулями ядра (kext) в macOS отличается от "
                       "Linux и здесь не поддерживается.")

    def firewall_status(self) -> str:
        parts: list[str] = []
        if os.path.exists(SOCKETFILTERFW):
            st = common.run_out([SOCKETFILTERFW, "--getglobalstate"], timeout=10)
            if st:
                parts.append("Application Firewall:\n" + st)
        pf = common.run_out(["pfctl", "-s", "info"], timeout=10)
        if pf:
            parts.append("pf (packet filter):\n" + pf[:2000])
        return "\n\n".join(parts) or \
            "Статус файрвола недоступен (возможно, нужны права администратора)"

    def firewall_status_root(self) -> str:
        parts: list[str] = []
        if os.path.exists(SOCKETFILTERFW):
            st = common.run_out([SOCKETFILTERFW, "--getglobalstate"],
                                root=True, timeout=15)
            if st:
                parts.append("Application Firewall:\n" + st)
        pf = common.run_out(["pfctl", "-s", "info"], root=True, timeout=15)
        if pf:
            parts.append("pf (packet filter):\n" + pf[:3000])
        return "\n\n".join(parts) or "Нечего показать"

    def journal_entries(self, priority: str = "err", lines: int = 200,
                        unit: str = "") -> str:
        try:
            count = max(1, min(int(lines), 2000))
        except (TypeError, ValueError):
            count = 200
        # log show бывает медленным — ограничиваем время ожидания.
        cmd = ["log", "show", "--last", "1h", "--style", "compact",
               "-n", str(count)]
        if unit:
            cmd += ["--predicate", f'process == "{unit}"']
        elif priority in ("err", "error", "crit", "alert", "emerg",
                          "0", "1", "2", "3"):
            cmd += ["--predicate", "messageType == error"]
        text = (common.run(cmd, timeout=30).stdout or "").strip()
        return text or "Записей нет"

    # ----------------------------------------------------------------- порты
    def listening_ports(self) -> list[dict]:
        r = common.run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"], timeout=20)
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines()[1:]:
            parts = line.split(None, 8)
            if len(parts) < 9:
                continue
            command, pid, _user, _fd, typ, _dev, _off, _node, name = parts
            rows.append({"proto": "tcp6" if "IPv6" in typ else "tcp",
                         "state": "LISTEN",
                         "local": name.replace(" (LISTEN)", "").strip(),
                         "proc": f"{command}({pid})"})
        return rows

    def established_connections(self) -> list[dict]:
        r = common.run(["lsof", "-nP", "-iTCP", "-sTCP:ESTABLISHED"],
                       timeout=20)
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines()[1:]:
            parts = line.split(None, 8)
            if len(parts) < 9:
                continue
            command, pid, _user, _fd, typ, _dev, _off, _node, name = parts
            conn = name.replace(" (ESTABLISHED)", "").strip()
            local, _, peer = conn.partition("->")
            rows.append({"proto": "tcp6" if "IPv6" in typ else "tcp",
                         "local": local.strip(), "peer": peer.strip(),
                         "proc": f"{command}({pid})"})
        return rows

    # ----------------------------------------------------------------- твики
    def get_swappiness(self) -> int:
        # В macOS нет аналога vm.swappiness — возвращаем значение по умолчанию.
        return 60

    def set_swappiness(self, value: int) -> bool:
        return False

    def cpu_governor(self) -> str:
        # В macOS нет governor как в Linux; показываем режим питания, если есть.
        text = common.run_out(["pmset", "-g"], timeout=10)
        for line in text.splitlines():
            if "powermode" in line.lower():
                return line.strip()
        return "— (в macOS нет governor, как в Linux)"

    def cpu_governors(self) -> list[str]:
        return []

    def set_cpu_governor(self, governor: str) -> bool:
        return False

    def thp_status(self) -> str:
        return "не поддерживается (macOS)"

    def zram_status(self) -> str:
        return "не поддерживается (macOS)"

    # --------------------------------------------------------------- корзина
    def trash_items(self) -> list[dict]:
        rows: list[dict] = []
        trash = Path.home() / ".Trash"
        if not trash.is_dir():
            return rows
        for entry in sorted(trash.iterdir()):
            try:
                st = entry.lstat()
            except OSError:
                continue
            try:
                date = datetime.datetime.fromtimestamp(st.st_mtime) \
                    .strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError, OverflowError):
                date = ""
            rows.append({"name": entry.name, "path": str(entry),
                         "date": date, "info": entry})
        return rows

    def empty_trash(self) -> tuple[bool, str]:
        trash = Path.home() / ".Trash"
        freed = 0
        if trash.is_dir():
            for entry in list(trash.iterdir()):
                try:
                    if entry.is_dir() and not entry.is_symlink():
                        freed += common.dir_size(entry)
                        shutil.rmtree(entry, ignore_errors=True)
                    else:
                        freed += entry.lstat().st_size
                        entry.unlink(missing_ok=True)
                except OSError:
                    pass
        return True, f"Корзина очищена (~{common.human(freed)})"


def _plist_label(path: Path) -> str:
    """Извлекает значение <key>Label</key><string>…</string> из plist."""
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return ""
    m = re.search(r"<key>Label</key>\s*<string>([^<]+)</string>", text)
    return m.group(1).strip() if m else ""
