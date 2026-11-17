"""Linux-бэкенд: systemd, менеджеры пакетов, /proc, /sys, lm-sensors, XDG-autostart.

Работа с пакетами делегируется модулю `linux_pkg`, который сам определяет
дистрибутив (pacman/apt/dnf/zypper/apk) — поэтому программа работает не только
на Arch.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import urllib.parse
from pathlib import Path

from . import common, linux_pkg
from .base import BaseBackend

AUTOSTART_USER = Path.home() / ".config" / "autostart"
AUTOSTART_SYSTEM = Path("/etc/xdg/autostart")


class LinuxBackend(BaseBackend):
    name = "linux"
    display = "Linux"

    # ------------------------------------------------------------ процессы
    def list_processes(self) -> list[dict]:
        r = common.run(["ps", "-eo", "pid,user,pcpu,pmem,rss,comm,args",
                        "--sort=-pcpu", "--no-headers"])
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            parts = line.split(None, 6)
            if len(parts) < 7:
                continue
            pid, user, pcpu, pmem, rss, comm, args = parts
            try:
                rows.append({"pid": int(pid), "user": user, "cpu": float(pcpu),
                             "mem": float(pmem), "rss": int(rss), "name": comm,
                             "cmd": args})
            except ValueError:
                continue
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
            r = common.run(["kill", "-9" if force else "-15", str(pid)], root=True)
            ok = r.returncode == 0
            return ok, (f"{label} через pkexec → PID {pid}" if ok
                        else "нужны права root")

    # --------------------------------------------------------------- службы
    def list_services(self) -> list[dict]:
        r = common.run(["systemctl", "list-units", "--type=service", "--all",
                        "--no-pager", "--no-legend", "--plain"])
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            line = line.replace("●", " ").strip()
            if not line:
                continue
            parts = line.split(None, 4)
            if len(parts) < 4:
                continue
            unit, load, active, sub = parts[:4]
            desc = parts[4] if len(parts) > 4 else ""
            if not unit.endswith(".service") or load == "not-found":
                continue
            rows.append({"unit": unit, "load": load, "active": active,
                         "sub": sub, "desc": desc})
        return rows

    def service_action(self, unit: str, action: str) -> tuple[bool, str]:
        r = common.run(["systemctl", action, unit], root=True)
        ok = r.returncode == 0
        return ok, f"systemctl {action} {unit}" + ("" if ok else " — ошибка")

    # --------------------------------------------------------------- пакеты
    def package_manager(self) -> str:
        return linux_pkg.detect().key

    def search_packages(self, query: str) -> list[dict]:
        return linux_pkg.detect().search(query)

    def install_packages(self, names: list[str]) -> tuple[bool, str]:
        return linux_pkg.detect().install(names)

    def remove_packages(self, names: list[str]) -> tuple[bool, str]:
        return linux_pkg.detect().remove(names)

    def package_files(self, pkg: str) -> str:
        return linux_pkg.detect().files(pkg)

    def file_owner(self, path: str) -> str:
        return linux_pkg.detect().owner(path)

    def package_info(self, pkg: str) -> str:
        return linux_pkg.detect().info(pkg)

    # ----------------------------------------------------------- обновления
    def check_updates(self) -> list[dict]:
        return linux_pkg.detect().updates()

    def system_update(self) -> tuple[bool, str]:
        return linux_pkg.detect().upgrade()

    # ----------------------------------------------------------------- сеть
    def network_info(self) -> dict:
        info: dict = {"hostname": os.uname().nodename, "interfaces": [],
                      "route": "", "dns": []}
        r = common.run(["ip", "-brief", "addr"])
        for line in (r.stdout or "").splitlines():
            parts = line.split()
            if not parts:
                continue
            name = parts[0]
            state = parts[1] if len(parts) > 1 else ""
            addrs = parts[2:]
            info["interfaces"].append({
                "name": name, "state": state, "addrs": addrs,
                "mac": common.read_text(f"/sys/class/net/{name}/address")})
        info["route"] = common.run_out(["ip", "route", "show", "default"])
        try:
            for line in Path("/etc/resolv.conf").read_text().splitlines():
                if line.startswith("nameserver"):
                    info["dns"].append(line.split()[1])
        except OSError:
            pass
        return info

    # -------------------------------------------------------------- датчики
    def sensors_info(self) -> tuple[list, list]:
        temps: list[tuple[str, float]] = []
        fans: list[tuple[str, float]] = []
        if shutil.which("sensors"):
            r = common.run(["sensors", "-j"])
            try:
                data = json.loads(r.stdout or "{}")
            except (ValueError, TypeError):
                data = {}
            for chip, feats in data.items():
                if not isinstance(feats, dict):
                    continue
                for feat, vals in feats.items():
                    if not isinstance(vals, dict):
                        continue
                    for key, val in vals.items():
                        if not isinstance(val, (int, float)):
                            continue
                        label = f"{chip} · {feat}"
                        if key.endswith("_input") and "temp" in key:
                            temps.append((label, float(val)))
                        elif key.endswith("_input") and "fan" in key:
                            fans.append((label, float(val)))
        if not temps:
            for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
                try:
                    value = int(common.read_text(zone / "temp")) / 1000.0
                    kind = common.read_text(zone / "type") or zone.name
                    temps.append((f"{kind} ({zone.name})", value))
                except (ValueError, OSError):
                    continue
        return temps, fans

    def memory_info(self) -> tuple[float, float]:
        info: dict[str, int] = {}
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                key, _, value = line.partition(":")
                info[key] = int(value.split()[0])
        except (OSError, ValueError, IndexError):
            return 0.0, 0.0
        total = info.get("MemTotal", 0) / 1024 / 1024
        avail = info.get("MemAvailable", info.get("MemFree", 0)) / 1024 / 1024
        return total, total - avail

    def load_avg(self) -> tuple[float, float, float]:
        try:
            a, b, c = Path("/proc/loadavg").read_text().split()[:3]
            return float(a), float(b), float(c)
        except (OSError, ValueError):
            return 0.0, 0.0, 0.0

    def cpu_percent(self) -> float:
        def snap():
            try:
                vals = list(map(int, Path("/proc/stat").read_text()
                                .splitlines()[0].split()[1:]))
                idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
                return idle, sum(vals)
            except (OSError, ValueError, IndexError):
                return 0, 0
        if not hasattr(self, "_cpu_last"):
            self._cpu_last = snap()
            return 0.0
        idle, total = snap()
        di, dt = idle - self._cpu_last[0], total - self._cpu_last[1]
        self._cpu_last = (idle, total)
        if dt <= 0:
            return 0.0
        return max(0.0, min(100.0, 100.0 * (1 - di / dt)))

    def uptime(self) -> str:
        try:
            secs = float(Path("/proc/uptime").read_text().split()[0])
        except (OSError, ValueError, IndexError):
            return "—"
        h, m = divmod(int(secs) // 60, 60)
        d, h = divmod(h, 24)
        return f"{d} д {h} ч {m} мин" if d else f"{h} ч {m} мин"

    def cpu_model(self) -> str:
        for line in common.read_text("/proc/cpuinfo").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
        import platform
        return platform.processor() or "CPU"

    def battery_info(self) -> dict | None:
        bats = sorted(Path("/sys/class/power_supply").glob("BAT*"))
        if not bats:
            return None
        bat = bats[0]
        return {"name": bat.name,
                "capacity": common.read_text(bat / "capacity") or "—",
                "status": common.read_text(bat / "status") or "—",
                "health": common.read_text(bat / "health") or "—",
                "energy_now": common.read_text(bat / "energy_now"),
                "energy_full": common.read_text(bat / "energy_full")}

    # ------------------------------------------------------------- автозапуск
    def list_startup(self) -> list[dict]:
        rows: list[dict] = []
        for folder in (AUTOSTART_USER, AUTOSTART_SYSTEM):
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.desktop")):
                data = _parse_desktop(path)
                if not data:
                    continue
                hidden = data.get("Hidden", "false").lower() == "true"
                gnome = data.get("X-GNOME-Autostart-enabled", "true").lower() != "false"
                rows.append({"name": data.get("Name", path.stem),
                             "exec": data.get("Exec", ""),
                             "enabled": (not hidden) and gnome,
                             "source": "пользователь" if folder == AUTOSTART_USER
                             else "система",
                             "path": path})
        return rows

    def set_startup_enabled(self, entry: dict, enabled: bool) -> bool:
        AUTOSTART_USER.mkdir(parents=True, exist_ok=True)
        target = AUTOSTART_USER / entry["path"].name
        if entry["source"] == "пользователь":
            try:
                text = entry["path"].read_text(errors="ignore")
            except OSError:
                return False
            lines = [ln for ln in text.splitlines()
                     if not ln.strip().lower().startswith("hidden=")]
            lines.append(f"Hidden={'false' if enabled else 'true'}")
            return common.write_text(target, "\n".join(lines) + "\n")
        data = _parse_desktop(entry["path"]) or {}
        content = ["[Desktop Entry]", "Type=Application",
                   f"Name={data.get('Name', entry['name'])}",
                   f"Exec={data.get('Exec', entry['exec'])}",
                   f"Hidden={'false' if enabled else 'true'}", ""]
        return common.write_text(target, "\n".join(content))

    # ------------------------------------------------------------------ диск
    def root_path(self) -> str:
        return "/"

    def mounts(self) -> list[dict]:
        rows: list[dict] = []
        skip = {"proc", "sysfs", "devtmpfs", "cgroup", "cgroup2", "securityfs",
                "debugfs", "tracefs", "pstore", "configfs", "fusectl", "mqueue",
                "hugetlbfs", "binfmt_misc", "autofs", "efivarfs", "bpf"}
        try:
            for line in Path("/proc/mounts").read_text().splitlines():
                parts = line.split()
                if len(parts) < 4:
                    continue
                src, target, fstype, opts = parts[:4]
                if fstype in skip:
                    continue
                rows.append({"src": src, "target": target, "fstype": fstype,
                             "opts": opts})
        except OSError:
            pass
        return rows

    def disks_overview(self) -> str:
        lsblk = common.run_out(["lsblk", "-o",
                                "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL",
                                "-e", "7"])
        df = common.run_out(["df", "-h", "-x", "tmpfs", "-x", "devtmpfs"])
        return (f"Устройства:\n{lsblk or '—'}\n\n"
                f"Использование файловых систем:\n{df or '—'}")

    def smart_health(self) -> str:
        if not shutil.which("smartctl"):
            return "smartctl не установлен (пакет smartmontools)"
        devices: list[Path] = []
        for pattern in ("sd*", "nvme*", "vd*"):
            for dev in sorted(Path("/dev").glob(pattern)):
                if dev.name[-1].isdigit():
                    continue
                devices.append(dev)
        if not devices:
            return "Накопители не найдены"
        out: list[str] = []
        for dev in devices:
            text = common.run_out(["smartctl", "-H", "-A", str(dev)], root=True)
            out.append(f"=== {dev} ===\n{text[:2500] or 'нет данных (нужны права root)'}")
        return "\n\n".join(out)

    # ----------------------------------------------------------- железо и пр.
    def hardware_sections(self) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        for cmd, title_text in ((["lscpu"], "Процессор"),
                                (["lspci"], "Устройства PCI"),
                                (["lsusb"], "USB")):
            text = common.run_out(cmd)
            if text:
                sections.append((title_text, text))
        block = common.run_out(["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT"])
        if block:
            sections.append(("Накопители", block))
        total, used = self.memory_info()
        sections.append(("Память", f"Всего: {total:.1f} ГБ\nИспользовано: {used:.1f} ГБ"))
        return sections

    def diagnostics(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        failed = common.run_out(["systemctl", "--failed", "--no-pager",
                                 "--no-legend", "--plain"])
        out.append(("Упавшие службы", failed or "нет — всё в порядке"))
        errs = common.run_out(["journalctl", "-p", "err", "-b", "--no-pager",
                               "-n", "40"])
        out.append(("Ошибки в журнале (текущая загрузка)", errs or "нет"))
        fstrim = common.run_out(["systemctl", "status", "fstrim.timer", "--no-pager"])
        out.append(("TRIM (fstrim.timer)", fstrim or "таймер не найден"))
        if Path("/var/run/reboot-required").exists():
            out.append(("Перезагрузка", "требуется перезагрузка"))
        return out

    def boot_analysis(self) -> list[tuple[str, str]]:
        return [("Время загрузки",
                 common.run_out(["systemd-analyze"]) or "systemd-analyze недоступен"),
                ("Самые медленные юниты",
                 common.run_out(["systemd-analyze", "blame", "--no-pager"])[:5000]
                 or "нет данных"),
                ("Критическая цепочка",
                 common.run_out(["systemd-analyze", "critical-chain",
                                 "--no-pager"])[:5000] or "нет данных")]

    def list_timers_raw(self) -> str:
        text = common.run_out(["systemctl", "list-timers", "--all", "--no-pager",
                               "--no-legend", "--plain"])
        if not text:
            return "Активных таймеров нет"
        lines = ["NEXT  LEFT  LAST  PASSED  UNIT  ACTIVATES"]
        lines += [" ".join(ln.split()) for ln in text.splitlines()]
        return "\n".join(lines)

    def list_modules(self) -> list[dict]:
        r = common.run(["lsmod"])
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines()[1:]:
            parts = line.split(None, 3)
            if len(parts) < 3:
                continue
            name, size, used = parts[:3]
            rows.append({"name": name, "size": size, "used": used,
                         "by": parts[3] if len(parts) > 3 else ""})
        return rows

    def module_action(self, name: str, action: str) -> tuple[bool, str]:
        cmd = ["modprobe", name] if action == "load" else ["modprobe", "-r", name]
        r = common.run(cmd, root=True)
        verb = "загружен" if action == "load" else "выгружен"
        return r.returncode == 0, (f"{name}: {verb}" if r.returncode == 0
                                   else f"{name}: не удалось (нужны права root)")

    def firewall_status(self) -> str:
        parts: list[str] = []
        for svc in ("ufw", "firewalld", "nftables", "iptables"):
            state = common.run_out(["systemctl", "is-active", svc])
            if state:
                parts.append(f"Служба {svc}: {state}")
        if shutil.which("ufw"):
            parts.append("ufw status (без root):\n" +
                         (common.run_out(["ufw", "status"]) or "нужны права root"))
        if shutil.which("nft"):
            rules = common.run_out(["nft", "list", "ruleset"])
            if rules:
                parts.append("nftables ruleset:\n" + rules[:3000])
        if shutil.which("iptables"):
            rules = common.run_out(["iptables", "-S"])
            if rules:
                parts.append("iptables -S:\n" + rules[:3000])
        return "\n\n".join(parts) or "Утилиты файрвола не найдены"

    def firewall_status_root(self) -> str:
        if shutil.which("ufw"):
            return common.run_out(["ufw", "status", "verbose"], root=True)
        if shutil.which("firewall-cmd"):
            return common.run_out(["firewall-cmd", "--list-all"], root=True)
        if shutil.which("nft"):
            return common.run_out(["nft", "list", "ruleset"], root=True)
        return "Нечего показать"

    def journal_entries(self, priority: str = "err", lines: int = 200,
                        unit: str = "") -> str:
        cmd = ["journalctl", "--no-pager", "-n", str(lines), "-p", priority]
        if unit:
            cmd += ["-u", unit]
        return common.run_out(cmd) or "Записей нет"

    # ----------------------------------------------------------------- порты
    def listening_ports(self) -> list[dict]:
        r = common.run(["ss", "-tulpn"])
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines()[1:]:
            parts = line.split(None, 5)
            if len(parts) < 5:
                continue
            proto, state, _recv, _send, local = parts[:5]
            rows.append({"proto": proto, "state": state, "local": local,
                         "proc": parts[5] if len(parts) > 5 else ""})
        return rows

    def established_connections(self) -> list[dict]:
        r = common.run(["ss", "-tunp", "state", "established"])
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines()[1:]:
            parts = line.split(None, 5)
            if len(parts) < 5:
                continue
            proto, _state, _r, _s, local = parts[:5]
            rows.append({"proto": proto, "local": local,
                         "peer": parts[4] if len(parts) > 4 else "",
                         "proc": parts[5] if len(parts) > 5 else ""})
        return rows

    # ----------------------------------------------------------------- твики
    def get_swappiness(self) -> int:
        try:
            return int(common.read_text("/proc/sys/vm/swappiness"))
        except ValueError:
            return 60

    def set_swappiness(self, value: int) -> bool:
        return common.run(["sysctl", "-w", f"vm.swappiness={value}",
                           ], root=True).returncode == 0

    def cpu_governor(self) -> str:
        return common.read_text(
            "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor") or "—"

    def cpu_governors(self) -> list[str]:
        raw = common.read_text(
            "/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors")
        return raw.split() if raw else []

    def set_cpu_governor(self, governor: str) -> bool:
        cmd = ["sh", "-c",
               "for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; "
               f"do echo {governor} > $f; done"]
        return common.run(cmd, root=True).returncode == 0

    def thp_status(self) -> str:
        return common.read_text("/sys/kernel/mm/transparent_hugepage/enabled") or "—"

    def zram_status(self) -> str:
        zrams = sorted(Path("/sys/block").glob("zram*"))
        if not zrams:
            return "не используется"
        return common.run_out(["swapon", "--show"]) or f"{len(zrams)} устройств(а) zram"

    # --------------------------------------------------------------- корзина
    def trash_items(self) -> list[dict]:
        rows: list[dict] = []
        info_dir = Path.home() / ".local" / "share" / "Trash" / "info"
        if not info_dir.is_dir():
            return rows
        for info in sorted(info_dir.glob("*.trashinfo")):
            path = date = ""
            try:
                for line in info.read_text(errors="ignore").splitlines():
                    if line.startswith("Path="):
                        path = urllib.parse.unquote(line[5:])
                    elif line.startswith("DeletionDate="):
                        date = line[13:]
            except OSError:
                continue
            rows.append({"name": Path(path).name or info.stem, "path": path,
                         "date": date, "info": info})
        return rows

    def empty_trash(self) -> tuple[bool, str]:
        trash = Path.home() / ".local" / "share" / "Trash"
        freed = 0
        for sub in ("files", "info", "expunged"):
            folder = trash / sub
            if not folder.is_dir():
                continue
            for entry in list(folder.iterdir()):
                try:
                    if entry.is_dir() and not entry.is_symlink():
                        freed += common.dir_size(entry)
                        shutil.rmtree(entry, ignore_errors=True)
                    else:
                        freed += entry.stat().st_size
                        entry.unlink(missing_ok=True)
                except OSError:
                    pass
        return True, f"Корзина очищена (~{common.human(freed)})"


def _parse_desktop(path: Path) -> dict | None:
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return None
    data: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "[")):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            data[key.strip()] = value.strip()
    return data
