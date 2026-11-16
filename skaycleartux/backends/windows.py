"""Windows-бэкенд: PowerShell, CIM/WMI, sc, tasklist, netstat, winget, реестр.

Всё, что можно, делается через встроенные средства Windows. Любая функция
деградирует мягко: при отсутствии утилиты, прав или данных возвращается
безопасное значение, а не исключение.
"""
from __future__ import annotations

import os
import re

from . import common
from .base import BaseBackend

NOT_AVAILABLE = "Недоступно в Windows"


# --------------------------------------------------------------------------- #
#  Вспомогательные функции
# --------------------------------------------------------------------------- #
def _ps_exe() -> str:
    """Путь к PowerShell (powershell.exe или pwsh), иначе просто имя."""
    return common.which("powershell") or common.which("pwsh") or "powershell"


def _ps(script: str, timeout: float = 25.0) -> str:
    """Выполняет PowerShell-скрипт и возвращает stdout без хвостовых пробелов."""
    try:
        r = common.run([_ps_exe(), "-NoProfile", "-Command", script],
                       timeout=timeout)
    except Exception:  # noqa: BLE001 — бэкенд не должен падать
        return ""
    return (r.stdout or "").strip()


def _num(text, default: float = 0.0) -> float:
    """Разбор числа с учётом локали (запятая как десятичный разделитель)."""
    try:
        return float(str(text).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default


def _int(text, default: int = 0) -> int:
    try:
        return int(_num(text, float(default)))
    except (TypeError, ValueError):
        return default


def _split_cols(line: str) -> list[str]:
    """Разбивает строку таблицы winget по двум и более пробелам."""
    return [c.strip() for c in re.split(r"\s{2,}", line.rstrip())]


def _cell(row: dict, *names: str, default: str = "") -> str:
    """Значение колонки по любому из возможных имён (учёт локали winget)."""
    for name in names:
        value = row.get(name)
        if value:
            return value
    return default


def _winget_parse(text: str) -> list[dict]:
    """Разбирает текстовую таблицу winget в список словарей (колонки — ключи)."""
    header: list[str] | None = None
    rows: list[dict] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if set(stripped) <= {"-", " "}:
            continue
        cells = _split_cols(line)
        if not cells:
            continue
        low = [c.lower() for c in cells]
        if header is None:
            if ("name" in low or "имя" in low) and \
                    ("id" in low or "идентификатор" in low):
                header = low
            continue
        low_s = stripped.lower()
        # служебные строки-итоги
        if low_s.startswith(("no installed", "no package", "the following",
                             "no applicable", "установленных", "пакеты")):
            continue
        if "upgrades available" in low_s or \
                ("обновлен" in low_s and "доступн" in low_s):
            continue
        if len(cells) < 2:
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def _parse_ipconfig(text: str) -> dict:
    """Разбор `ipconfig /all` (терпим к русской локали и IPv6)."""
    hostname = os.environ.get("COMPUTERNAME", "")
    interfaces: list[dict] = []
    route: list[str] = []
    dns: list[str] = []
    cur: dict | None = None
    last_key = ""

    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if not line[:1].isspace():
            # новый раздел (адаптер или «Windows IP Configuration»)
            if cur is not None:
                interfaces.append(cur)
                cur = None
            header = line.rstrip(":").strip()
            low = header.lower()
            if "ip configuration" in low or "конфигурация ip" in low:
                continue
            cur = {"name": header, "state": "up", "addrs": [], "mac": ""}
            last_key = ""
            continue
        if ":" not in line:
            # продолжение предыдущего значения (например, второй DNS)
            cont = line.strip()
            if cont and last_key == "dns":
                dns.append(cont)
            continue
        key, _, value = line.partition(":")
        key = key.strip().rstrip(".").strip()
        value = value.strip()
        kl = key.lower()
        if not value:
            continue
        if "physical address" in kl or "физический адрес" in kl:
            if cur is not None:
                cur["mac"] = value
            last_key = "mac"
        elif "ipv4" in kl:
            if cur is not None:
                cur["addrs"].append(value.split("(")[0].strip())
            last_key = "ipv4"
        elif "ipv6" in kl and "address" in kl:
            if cur is not None:
                cur["addrs"].append(value.split("(")[0].strip())
            last_key = "ipv6"
        elif "default gateway" in kl or "основной шлюз" in kl:
            route.append(value)
            last_key = "gw"
        elif "dns servers" in kl or "dns-сервер" in kl:
            dns.append(value)
            last_key = "dns"
        elif "host name" in kl or "имя узла" in kl:
            hostname = value or hostname
            last_key = "host"
        elif "media state" in kl or "состояние среды" in kl:
            if cur is not None:
                cur["state"] = "down"
            last_key = "media"
        else:
            last_key = "other"

    if cur is not None:
        interfaces.append(cur)
    return {"hostname": hostname, "interfaces": interfaces,
            "route": ", ".join(route), "dns": dns}


class WindowsBackend(BaseBackend):
    name = "windows"
    display = "Windows"

    # ------------------------------------------------------------ процессы
    def list_processes(self) -> list[dict]:
        script = (
            "$d=[char]9;"
            "$total=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory;"
            "Write-Output ('T'+$d+$total);"
            "$gp=@{};"
            "Get-Process -ErrorAction SilentlyContinue|"
            "ForEach-Object{$gp[[int]$_.Id]=$_};"
            "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue|"
            "ForEach-Object{"
            "$g=$gp[[int]$_.ProcessId];"
            "$cpu=0;if($g -ne $null -and $g.CPU -ne $null){$cpu=$g.CPU};"
            "$ws=0;if($g -ne $null -and $g.WorkingSet64 -ne $null)"
            "{$ws=$g.WorkingSet64};"
            "$cl=$_.CommandLine;if(-not $cl){$cl=$_.Name};"
            "Write-Output ('P'+$d+$_.ProcessId+$d+$_.Name+$d+$cpu+$d+$ws+$d+$cl)"
            "}"
        )
        out = _ps(script, timeout=40)
        rows: list[dict] = []
        total_bytes = 0.0
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0] == "T":
                total_bytes = _num(parts[1])
                continue
            if len(parts) < 6 or parts[0] != "P":
                continue
            pid = _int(parts[1], -1)
            if pid < 0:
                continue
            rss = _int(parts[4])
            mem = (rss / total_bytes * 100.0) if total_bytes else 0.0
            rows.append({"pid": pid, "user": "", "cpu": round(_num(parts[3]), 1),
                         "mem": round(mem, 2), "rss": rss, "name": parts[2],
                         "cmd": "\t".join(parts[5:])})
        rows.sort(key=lambda r: (r["cpu"], r["rss"]), reverse=True)
        return rows

    def kill_process(self, pid: int, force: bool = False) -> tuple[bool, str]:
        cmd = ["taskkill", "/PID", str(pid)]
        if force:
            cmd.append("/F")
        r = common.run(cmd, timeout=20)
        ok = r.returncode == 0
        label = "taskkill /F" if force else "taskkill"
        if ok:
            return True, f"{label} → PID {pid}"
        return False, f"не удалось завершить PID {pid} (нужны права?)"

    # --------------------------------------------------------------- службы
    def list_services(self) -> list[dict]:
        script = (
            "$d=[char]9;"
            "Get-Service -ErrorAction SilentlyContinue|ForEach-Object{"
            "Write-Output ('S'+$d+$_.Name+$d+$_.Status+$d+$_.DisplayName)}"
        )
        out = _ps(script, timeout=30)
        rows: list[dict] = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 3 or parts[0] != "S":
                continue
            status = parts[2]
            rows.append({"unit": parts[1], "load": "service", "active": status,
                         "sub": status,
                         "desc": "\t".join(parts[3:]) if len(parts) > 3 else ""})
        return rows

    def service_action(self, unit: str, action: str) -> tuple[bool, str]:
        name = (unit or "").strip()
        if not name:
            return False, "Укажи имя службы"

        def sc(*args: str) -> tuple[bool, str]:
            r = common.run(["sc", *args], timeout=40)
            return r.returncode == 0, (r.stdout or "").strip()

        if action in ("start", "stop"):
            ok, out = sc(action, name)
            return ok, (out or f"sc {action} {name}" +
                        ("" if ok else " — ошибка"))
        if action == "restart":
            sc("stop", name)
            ok, out = sc("start", name)
            return ok, (out or f"{name}: перезапуск" +
                        ("" if ok else " — ошибка"))
        if action == "enable":
            ok, _ = sc("config", name, "start=", "auto")
            return ok, (f"{name}: автозапуск включён" if ok
                        else f"{name}: не удалось (нужны права)")
        if action == "disable":
            ok, _ = sc("config", name, "start=", "demand")
            return ok, (f"{name}: автозапуск отключён" if ok
                        else f"{name}: не удалось (нужны права)")
        return False, f"Неизвестное действие: {action}"

    # --------------------------------------------------------------- пакеты
    def package_manager(self) -> str:
        if common.which("winget"):
            return "winget"
        if common.which("choco"):
            return "choco"
        return ""

    def _winget_installed_ids(self) -> set[str]:
        wg = common.which("winget")
        if not wg:
            return set()
        r = common.run([wg, "list", "--accept-source-agreements"], timeout=90)
        ids: set[str] = set()
        for row in _winget_parse(r.stdout or ""):
            pid = _cell(row, "id", "идентификатор")
            if pid:
                ids.add(pid.strip().lower())
        return ids

    def search_packages(self, query: str) -> list[dict]:
        q = (query or "").strip()
        wg = common.which("winget")
        if not q or not wg:
            return []
        r = common.run([wg, "search", "--accept-source-agreements", q],
                       timeout=90)
        installed = self._winget_installed_ids()
        rows: list[dict] = []
        for row in _winget_parse(r.stdout or ""):
            name = _cell(row, "name", "имя")
            pid = _cell(row, "id", "идентификатор")
            if not name and not pid:
                continue
            match = _cell(row, "match", "совпадение")
            rows.append({
                "name": name or pid,
                "version": _cell(row, "version", "версия"),
                "repo": _cell(row, "source", "источник"),
                "installed": bool(pid) and pid.strip().lower() in installed,
                "desc": match or (f"Id: {pid}" if pid else ""),
            })
        return rows

    def install_packages(self, names: list[str]) -> tuple[bool, str]:
        pkgs = [n for n in (names or []) if n and n.strip()]
        if not pkgs:
            return False, "Укажи пакет(ы)"
        wg = common.which("winget")
        if wg:
            r = common.run([wg, "install", "--silent",
                            "--accept-package-agreements",
                            "--accept-source-agreements", *pkgs], timeout=1800)
            return r.returncode == 0, (r.stdout or "").strip()[-4000:]
        ch = common.which("choco")
        if ch:
            r = common.run([ch, "install", "-y", *pkgs], timeout=1800)
            return r.returncode == 0, (r.stdout or "").strip()[-4000:]
        return False, "winget/choco не найдены"

    def remove_packages(self, names: list[str]) -> tuple[bool, str]:
        pkgs = [n for n in (names or []) if n and n.strip()]
        if not pkgs:
            return False, "Укажи пакет(ы)"
        wg = common.which("winget")
        if wg:
            r = common.run([wg, "uninstall", "--silent",
                            "--accept-source-agreements", *pkgs], timeout=900)
            return r.returncode == 0, (r.stdout or "").strip()[-4000:]
        ch = common.which("choco")
        if ch:
            r = common.run([ch, "uninstall", "-y", *pkgs], timeout=900)
            return r.returncode == 0, (r.stdout or "").strip()[-4000:]
        return False, "winget/choco не найдены"

    def package_files(self, pkg: str) -> str:
        return NOT_AVAILABLE

    def file_owner(self, path: str) -> str:
        return NOT_AVAILABLE

    def package_info(self, pkg: str) -> str:
        name = (pkg or "").strip()
        if not name:
            return "Укажи имя пакета"
        wg = common.which("winget")
        if wg:
            r = common.run([wg, "show", "--accept-source-agreements", name],
                           timeout=60)
            out = (r.stdout or "").strip()
            if out:
                return out[:8000]
        ch = common.which("choco")
        if ch:
            out = common.run_out([ch, "info", name], timeout=60)
            if out:
                return out[:8000]
        return "Пакет не найден"

    # ----------------------------------------------------------- обновления
    def check_updates(self) -> list[dict]:
        wg = common.which("winget")
        if not wg:
            return []
        r = common.run([wg, "upgrade", "--accept-source-agreements"], timeout=120)
        rows: list[dict] = []
        for row in _winget_parse(r.stdout or ""):
            name = _cell(row, "name", "имя")
            new = _cell(row, "available", "доступно", "доступная версия")
            if name and new:
                rows.append({"name": name,
                             "old": _cell(row, "version", "версия"),
                             "new": new})
        return rows

    def system_update(self) -> tuple[bool, str]:
        wg = common.which("winget")
        if wg:
            r = common.run([wg, "upgrade", "--all", "--silent",
                            "--accept-package-agreements",
                            "--accept-source-agreements"], timeout=3600)
            return r.returncode == 0, (r.stdout or "").strip()[-6000:]
        ch = common.which("choco")
        if ch:
            r = common.run([ch, "upgrade", "all", "-y"], timeout=3600)
            return r.returncode == 0, (r.stdout or "").strip()[-6000:]
        return False, "winget/choco не найдены"

    # ----------------------------------------------------------------- сеть
    def network_info(self) -> dict:
        r = common.run(["ipconfig", "/all"], timeout=25)
        try:
            return _parse_ipconfig(r.stdout or "")
        except Exception:  # noqa: BLE001
            return {"hostname": os.environ.get("COMPUTERNAME", ""),
                    "interfaces": [], "route": "", "dns": []}

    def public_ip(self) -> str:
        for url in ("https://api.ipify.org", "https://ifconfig.me/ip",
                    "https://icanhazip.com"):
            out = _ps("(Invoke-RestMethod -Uri '" + url + "' -TimeoutSec 6)",
                      timeout=12)
            ip = out.strip().splitlines()[-1].strip() if out else ""
            if ip and len(ip) < 46 and " " not in ip:
                return ip
        return super().public_ip()

    # -------------------------------------------------------------- датчики
    def sensors_info(self) -> tuple[list, list]:
        temps: list[tuple[str, float]] = []
        script = (
            "$d=[char]9;"
            "Get-CimInstance -Namespace root/wmi "
            "-ClassName MSAcpi_ThermalZoneTemperature "
            "-ErrorAction SilentlyContinue|ForEach-Object{"
            "Write-Output ($_.InstanceName+$d+$_.CurrentTemperature)}"
        )
        out = _ps(script, timeout=25)
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            value = _num(parts[1], -9999.0)
            if value < -1000:
                continue
            celsius = value / 10.0 - 273.15
            if -60.0 <= celsius <= 200.0:
                temps.append((parts[0] or "Термозона", round(celsius, 1)))
        return temps, []

    def memory_info(self) -> tuple[float, float]:
        script = (
            "$os=Get-CimInstance Win32_OperatingSystem;"
            "Write-Output ($os.TotalVisibleMemorySize.ToString()+' '+"
            "$os.FreePhysicalMemory.ToString())"
        )
        out = _ps(script, timeout=20)
        parts = out.split()
        if len(parts) < 2:
            return 0.0, 0.0
        total_kb = _num(parts[0])
        free_kb = _num(parts[1])
        total = total_kb / 1024.0 / 1024.0
        used = (total_kb - free_kb) / 1024.0 / 1024.0
        return round(total, 2), round(used, 2)

    def load_avg(self) -> tuple[float, float, float]:
        return 0.0, 0.0, 0.0

    def cpu_percent(self) -> float:
        script = (
            "$c=Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue;"
            "if($c){($c|Measure-Object -Property LoadPercentage -Average)"
            ".Average}else{''}"
        )
        out = _ps(script, timeout=20)
        return max(0.0, min(100.0, _num(out, 0.0)))

    def uptime(self) -> str:
        script = (
            "$b=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime;"
            "((Get-Date)-$b).TotalSeconds"
        )
        out = _ps(script, timeout=20)
        secs = _num(out, -1.0)
        if secs < 0:
            return "—"
        h, m = divmod(int(secs) // 60, 60)
        d, h = divmod(h, 24)
        return f"{d} д {h} ч {m} мин" if d else f"{h} ч {m} мин"

    def cpu_model(self) -> str:
        out = _ps(
            "(Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue|"
            "Select-Object -First 1).Name", timeout=20)
        if out:
            return out.splitlines()[0].strip()
        import platform
        return platform.processor() or "CPU"

    def battery_info(self) -> dict | None:
        script = (
            "$d=[char]9;"
            "Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue|"
            "Select-Object -First 1|ForEach-Object{"
            "Write-Output ($_.Name+$d+$_.EstimatedChargeRemaining+$d+"
            "$_.Status)}"
        )
        out = _ps(script, timeout=20)
        if not out:
            return None
        parts = out.splitlines()[0].split("\t")
        if len(parts) < 3 or not parts[0].strip():
            return None
        status_map = {
            "1": "Разряжается", "2": "Подключён к сети",
            "3": "Полностью заряжен", "4": "Низкий заряд",
            "5": "Критический заряд", "6": "Заряжается",
            "7": "Заряжается (высокий)", "8": "Заряжается (низкий)",
            "9": "Заряжается (критический)", "10": "Неизвестно",
            "11": "Частично заряжен",
        }
        return {"name": parts[0].strip(), "capacity": parts[1].strip() or "—",
                "status": status_map.get(parts[2].strip(), parts[2].strip()),
                "health": "—", "energy_now": "", "energy_full": ""}

    # ------------------------------------------------------------- автозапуск
    def list_startup(self) -> list[dict]:
        script = (
            "$d=[char]9;"
            "$keys=@("
            "'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run',"
            "'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run',"
            "'HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Run');"
            "foreach($p in $keys){"
            "if(Test-Path $p){"
            "$item=Get-ItemProperty -Path $p -ErrorAction SilentlyContinue;"
            "$item.PSObject.Properties|Where-Object{$_.Name -notlike 'PS*'}|"
            "ForEach-Object{"
            "Write-Output ('R'+$d+$_.Name+$d+$_.Value+$d+$p)}}}"
            "$folders=@("
            "($env:APPDATA+'\\Microsoft\\Windows\\Start Menu\\Programs\\Startup'),"
            "($env:ProgramData+'\\Microsoft\\Windows\\Start Menu\\Programs\\Startup'));"
            "foreach($f in $folders){"
            "if(Test-Path $f){"
            "Get-ChildItem -Path $f -File -ErrorAction SilentlyContinue|"
            "ForEach-Object{"
            "Write-Output ('F'+$d+$_.Name+$d+$_.FullName+$d+$f)}}}"
        )
        out = _ps(script, timeout=25)
        rows: list[dict] = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            kind, name, value, src = parts[0], parts[1], parts[2], parts[3]
            if kind == "R":
                hive = "HKCU" if "HKCU" in src else "HKLM"
                rows.append({"name": name, "exec": value, "enabled": True,
                             "source": f"реестр ({hive})",
                             "path": src + "\\" + name})
            elif kind == "F":
                rows.append({"name": name, "exec": value,
                             "enabled": not name.lower().endswith(".disabled"),
                             "source": "папка «Автозагрузка»", "path": value})
        return rows

    def set_startup_enabled(self, entry: dict, enabled: bool) -> bool:
        try:
            path = str(entry.get("path", "") or "")
            source = str(entry.get("source", "") or "")
            if not path:
                return False
            # файл в папке «Автозагрузка»: переключаем суффикс .disabled
            if "Автозагрузка" in source and os.path.isfile(path):
                low = path.lower()
                if enabled and low.endswith(".disabled"):
                    os.replace(path, path[:-len(".disabled")])
                    return True
                if not enabled and not low.endswith(".disabled"):
                    os.replace(path, path + ".disabled")
                    return True
                return True
        except OSError:
            return False
        # записи в реестре: надёжного способа без правки StartupApproved нет
        return False

    # ------------------------------------------------------------------ диск
    def root_path(self) -> str:
        return os.environ.get("SystemDrive", "C:") + "\\"

    def mounts(self) -> list[dict]:
        script = (
            "$d=[char]9;"
            "$fs=@{};"
            "Get-CimInstance Win32_LogicalDisk -ErrorAction SilentlyContinue|"
            "ForEach-Object{$fs[$_.DeviceID]=$_.FileSystem};"
            "Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue|"
            "ForEach-Object{"
            "$k=$_.Name+':';"
            "Write-Output ('D'+$d+$_.Name+$d+$_.Root+$d+$_.Used+$d+$_.Free+$d+"
            "$fs[$k])}"
        )
        out = _ps(script, timeout=25)
        rows: list[dict] = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 5 or parts[0] != "D":
                continue
            used = _num(parts[3])
            free = _num(parts[4])
            rows.append({
                "src": parts[1], "target": parts[2],
                "fstype": parts[5] if len(parts) > 5 else "",
                "opts": f"занято {common.human(used)}, "
                        f"свободно {common.human(free)}",
            })
        return rows

    def disks_overview(self) -> str:
        script = (
            "Write-Output '=== LOGICAL ===';"
            "Get-CimInstance Win32_LogicalDisk -ErrorAction SilentlyContinue|"
            "Format-Table DeviceID,FileSystem,VolumeName,"
            "@{n='SizeGB';e={if($_.Size){[math]::Round($_.Size/1GB,1)}"
            "else{0}}},"
            "@{n='FreeGB';e={if($_.FreeSpace){"
            "[math]::Round($_.FreeSpace/1GB,1)}else{0}}} -AutoSize|"
            "Out-String|Write-Output;"
            "Write-Output '=== PHYSICAL ===';"
            "try{Get-Disk -ErrorAction Stop|Format-Table Number,FriendlyName,"
            "@{n='SizeGB';e={if($_.Size){[math]::Round($_.Size/1GB,1)}"
            "else{0}}},PartitionStyle,OperationalStatus -AutoSize|"
            "Out-String|Write-Output}"
            "catch{Get-Volume -ErrorAction SilentlyContinue|"
            "Format-Table DriveLetter,FileSystemLabel,FileSystem,"
            "@{n='SizeGB';e={if($_.Size){[math]::Round($_.Size/1GB,1)}"
            "else{0}}} -AutoSize|Out-String|Write-Output}"
        )
        out = _ps(script, timeout=30)
        if not out:
            return "Не удалось получить сведения о дисках"
        out = out.replace("=== LOGICAL ===", "Логические диски:")
        out = out.replace("=== PHYSICAL ===", "Физические диски:")
        return out[:6000]

    def smart_health(self) -> str:
        script = (
            "try{Get-PhysicalDisk -ErrorAction Stop|"
            "Get-StorageReliabilityCounter -ErrorAction Stop|"
            "Format-List *|Out-String|Write-Output}catch{}"
        )
        out = _ps(script, timeout=30)
        if not out:
            return ("Нет данных SMART (нужны права администратора "
                    "или диск не поддерживается)")
        return out[:6000]

    # ----------------------------------------------------------- железо и пр.
    def hardware_sections(self) -> list[tuple[str, str]]:
        script = (
            "Write-Output '###CPU###';"
            "Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue|"
            "Format-List Name,Manufacturer,NumberOfCores,"
            "NumberOfLogicalProcessors,MaxClockSpeed|Out-String|Write-Output;"
            "Write-Output '###GPU###';"
            "Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue|"
            "Format-List Name,DriverVersion,VideoProcessor,AdapterRAM|"
            "Out-String|Write-Output;"
            "Write-Output '###RAM###';"
            "Get-CimInstance Win32_PhysicalMemory -ErrorAction SilentlyContinue|"
            "Format-Table Manufacturer,Capacity,Speed,DeviceLocator -AutoSize|"
            "Out-String|Write-Output;"
            "Write-Output '###BOARD###';"
            "Get-CimInstance Win32_BaseBoard -ErrorAction SilentlyContinue|"
            "Format-List Manufacturer,Product,SerialNumber|Out-String|Write-Output"
        )
        out = _ps(script, timeout=40)
        sections: list[tuple[str, str]] = []
        titles = {"CPU": "Процессор", "GPU": "Видеокарта(ы)",
                  "RAM": "Оперативная память", "BOARD": "Материнская плата"}
        for key in ("CPU", "GPU", "RAM", "BOARD"):
            marker = f"###{key}###"
            if marker not in out:
                continue
            body = out.split(marker, 1)[1]
            for nxt in ("###CPU###", "###GPU###", "###RAM###", "###BOARD###"):
                if nxt != marker and nxt in body:
                    body = body.split(nxt, 1)[0]
            body = body.strip()
            if body:
                sections.append((titles[key], body[:4000]))
        total, used = self.memory_info()
        sections.append(("Память",
                         f"Всего: {total:.1f} ГБ\nИспользовано: {used:.1f} ГБ"))
        return sections

    def diagnostics(self) -> list[tuple[str, str]]:
        script = (
            "$d=[char]9;"
            "try{Get-WinEvent -FilterHashtable "
            "@{LogName='System';Level=1,2} -MaxEvents 30 -ErrorAction Stop|"
            "Format-Table TimeCreated,LevelDisplayName,ProviderName,Id,Message "
            "-Wrap|Out-String|Write-Output}"
            "catch{Write-Output 'нет данных'};"
            "Write-Output ('STOPPED'+$d+"
            "((Get-Service -ErrorAction SilentlyContinue|"
            "Where-Object{$_.Status -ne 'Running'}).Count))"
        )
        out = _ps(script, timeout=40)
        events = out
        stopped = "—"
        for line in out.splitlines():
            if line.startswith("STOPPED\t"):
                stopped = line.split("\t", 1)[1].strip()
                events = out.replace(line, "").strip()
                break
        return [("Ошибки и предупреждения (System, 30)",
                 (events or "нет данных")[:5000]),
                ("Службы не запущены", stopped)]

    def boot_analysis(self) -> list[tuple[str, str]]:
        script = (
            "$b=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime;"
            "Write-Output ('Загрузка: '+$b);"
            "Write-Output ('Прошло: '+((Get-Date)-$b));"
            "Write-Output '---';"
            "try{Get-WinEvent -FilterHashtable "
            "@{LogName='Microsoft-Windows-Diagnostics-Performance/Operational'}"
            " -MaxEvents 10 -ErrorAction Stop|"
            "Format-Table TimeCreated,Id,LevelDisplayName,Message -Wrap|"
            "Out-String|Write-Output}"
            "catch{Write-Output 'нет данных анализа загрузки'}"
        )
        out = _ps(script, timeout=40)
        if not out:
            return [("Анализ загрузки", NOT_AVAILABLE)]
        head, _, tail = out.partition("---")
        return [("Загрузка", head.strip()[:2000] or "—"),
                ("Анализ производительности загрузки",
                 tail.strip()[:5000] or "нет данных")]

    def list_timers_raw(self) -> str:
        r = common.run(["schtasks", "/query", "/fo", "LIST"], timeout=30)
        text = (r.stdout or "").strip()
        if not text:
            return "Задания не найдены или планировщик недоступен"
        return text[:8000]

    def list_modules(self) -> list[dict]:
        script = (
            "$d=[char]9;"
            "Get-CimInstance Win32_SystemDriver -ErrorAction SilentlyContinue|"
            "ForEach-Object{"
            "Write-Output ($_.Name+$d+$_.Size+$d+$_.State+$d+$_.PathName)}"
        )
        out = _ps(script, timeout=40)
        rows: list[dict] = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 3 or not parts[0]:
                continue
            rows.append({"name": parts[0], "size": parts[1],
                         "used": parts[2],
                         "by": parts[3] if len(parts) > 3 else ""})
        return rows

    def module_action(self, name: str, action: str) -> tuple[bool, str]:
        return False, ("Загрузка/выгрузка драйверов не поддерживается "
                       "(используй sc/pnputil вручную)")

    def firewall_status(self) -> str:
        script = (
            "Get-NetFirewallProfile -ErrorAction SilentlyContinue|"
            "Select-Object Name,Enabled|Format-Table -AutoSize|Out-String"
        )
        out = _ps(script, timeout=25)
        return out[:4000] or "Не удалось получить состояние файрвола"

    def firewall_status_root(self) -> str:
        return self.firewall_status()

    def journal_entries(self, priority: str = "err", lines: int = 200,
                        unit: str = "") -> str:
        n = max(1, min(_int(lines, 200), 2000))
        level = {"err": 2, "error": 2, "warning": 3, "warn": 3,
                 "info": 4, "information": 4}.get(str(priority).lower())
        if level:
            filt = " -FilterHashtable @{LogName='System';Level=" + str(level) + "}"
        else:
            filt = " -LogName System"
        script = ("Get-WinEvent" + filt + " -MaxEvents " + str(n) +
                  " -ErrorAction SilentlyContinue|"
                  "Format-Table TimeCreated,LevelDisplayName,ProviderName,Id,"
                  "Message -Wrap|Out-String")
        out = _ps(script, timeout=40)
        return (out[:8000] or "Записей нет")

    # ----------------------------------------------------------------- порты
    def listening_ports(self) -> list[dict]:
        r = common.run(["netstat", "-ano", "-p", "tcp"], timeout=25)
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            if parts[0].upper() != "TCP" or parts[3].upper() != "LISTENING":
                continue
            rows.append({"proto": parts[0], "state": parts[3],
                         "local": parts[1], "proc": parts[4]})
        return rows

    def established_connections(self) -> list[dict]:
        r = common.run(["netstat", "-ano", "-p", "tcp"], timeout=25)
        rows: list[dict] = []
        for line in (r.stdout or "").splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            if parts[0].upper() != "TCP" or parts[3].upper() != "ESTABLISHED":
                continue
            rows.append({"proto": parts[0], "local": parts[1],
                         "peer": parts[2], "proc": parts[4]})
        return rows

    # ----------------------------------------------------------------- твики
    def get_swappiness(self) -> int:
        return 60

    def set_swappiness(self, value: int) -> bool:
        return False

    def cpu_governor(self) -> str:
        out = common.run_out(["powercfg", "/getactivescheme"], timeout=15)
        if not out:
            return "—"
        if "(" in out and ")" in out:
            name = out[out.rfind("(") + 1:out.rfind(")")].strip()
            if name:
                return name
        return out.splitlines()[0].strip() or "—"

    def cpu_governors(self) -> list[str]:
        return []

    def set_cpu_governor(self, governor: str) -> bool:
        return False

    def thp_status(self) -> str:
        return "не поддерживается (Windows)"

    def zram_status(self) -> str:
        return "не поддерживается (Windows)"

    # --------------------------------------------------------------- корзина
    def trash_items(self) -> list[dict]:
        return []

    def empty_trash(self) -> tuple[bool, str]:
        r = common.run([_ps_exe(), "-NoProfile", "-Command",
                        "Clear-RecycleBin -Force -Confirm:$false "
                        "-ErrorAction SilentlyContinue"], timeout=180)
        if r.returncode == 0:
            return True, "Корзина очищена"
        return False, ("Не удалось очистить корзину "
                       "(возможно, она пуста или нужны права)")

