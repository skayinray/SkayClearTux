"""Юнит-тесты Windows-бэкенда (``skaycleartux.backends.windows``).

PowerShell не запускается: подменяем ``common.run`` и проверяем разбор
табличного вывода winget, ``ipconfig``, CIM-строк и корректную деградацию.
"""
from __future__ import annotations

import subprocess

import pytest

from skaycleartux.backends import windows
from skaycleartux.backends.windows import (
    WindowsBackend,
    _cell,
    _int,
    _num,
    _parse_ipconfig,
    _split_cols,
    _winget_parse,
)


def res(stdout="", code=0):
    return subprocess.CompletedProcess([], code, stdout, "")


@pytest.fixture
def backend():
    return WindowsBackend()


# --------------------------------------------------------------------------- #
#  Чистые вспомогательные функции
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,expected", [("1,5", 1.5), ("2.5", 2.5),
                                           ("bad", 0.0), (None, 0.0), ("", 0.0)])
def test_num(text, expected):
    assert _num(text) == expected


def test_int():
    assert _int("42") == 42
    assert _int("bad", default=-1) == -1


def test_split_cols():
    assert _split_cols("Name    Id    Version") == ["Name", "Id", "Version"]


def test_cell():
    row = {"Name": "x", "id": "y"}
    assert _cell(row, "id", "идентификатор") == "y"
    assert _cell(row, "missing", default="d") == "d"


def test_winget_parse():
    text = (
        "Name        Id            Version\n"
        "----------------------------------\n"
        "wget        GNU.Wget      1.0\n"
        "curl        cURL.cURL     8.0\n"
    )
    rows = _winget_parse(text)
    assert len(rows) == 2
    assert rows[0]["name"] == "wget"
    assert rows[0]["id"] == "GNU.Wget"


def test_winget_parse_ignores_summary():
    text = ("Name  Id  Version\n"
            "a  b  1\n"
            "2 upgrades available.\n")
    assert len(_winget_parse(text)) == 1


def test_parse_ipconfig():
    text = (
        "Windows IP Configuration\n"
        "\n"
        "   Host Name . . . . . . . . . . . . : mypc\n"
        "\n"
        "Ethernet adapter Ethernet:\n"
        "\n"
        "   Physical Address. . . . . . . . . : AA-BB-CC-DD-EE-FF\n"
        "   IPv4 Address. . . . . . . . . . . : 192.168.1.5(Preferred)\n"
        "   Default Gateway . . . . . . . . . : 192.168.1.1\n"
        "   DNS Servers . . . . . . . . . . . : 1.1.1.1\n"
        "                                       8.8.8.8\n"
    )
    info = _parse_ipconfig(text)
    assert info["hostname"] == "mypc"
    assert info["interfaces"][0]["mac"] == "AA-BB-CC-DD-EE-FF"
    assert info["interfaces"][0]["addrs"] == ["192.168.1.5"]
    assert info["route"] == "192.168.1.1"
    assert info["dns"] == ["1.1.1.1", "8.8.8.8"]


def test_parse_ipconfig_russian():
    text = (
        "Настройка протокола IP для Windows\n"
        "   Имя узла . . . . . . : ru-pc\n"
        "Адаптер Ethernet:\n"
        "   Физический адрес. . . : AA-BB\n"
        "   IPv4-адрес. . . . . . : 10.0.0.2\n"
        "   Основной шлюз . . . . : 10.0.0.1\n"
        "   DNS-серверы . . . . . : 9.9.9.9\n"
    )
    info = _parse_ipconfig(text)
    assert info["hostname"] == "ru-pc"
    assert info["interfaces"][0]["addrs"] == ["10.0.0.2"]
    assert info["route"] == "10.0.0.1"


# --------------------------------------------------------------------------- #
#  Процессы и службы
# --------------------------------------------------------------------------- #
def test_list_processes(backend, fake_run):
    out = ("T\t8000000\n"
           "P\t123\tchrome\t12.5\t4000000\tC:\\chrome.exe --type=gpu\n"
           "P\t456\tnotepad\t0\t1000000\tnotepad.exe\n")
    fake_run(default=res(out))
    rows = backend.list_processes()
    assert rows[0]["pid"] == 123
    assert rows[0]["name"] == "chrome"
    assert rows[0]["mem"] == 50.0  # 4 МБ из 8 МБ


def test_kill_process(backend, fake_run):
    fake_run(default=res("SUCCESS", 0))
    ok, msg = backend.kill_process(1, force=True)
    assert ok and "taskkill /F" in msg


def test_kill_process_fail(backend, fake_run):
    fake_run(default=res("ERROR", 1))
    ok, msg = backend.kill_process(1)
    assert ok is False and "не удалось" in msg


def test_list_services(backend, fake_run):
    out = "S\twuauserv\tRunning\tWindows Update\n"
    fake_run(default=res(out))
    rows = backend.list_services()
    assert rows[0]["unit"] == "wuauserv"
    assert rows[0]["active"] == "Running"


def test_service_action_start(backend, fake_run):
    fake_run(default=res("OK", 0))
    ok, msg = backend.service_action("wuauserv", "start")
    assert ok and "OK" in msg


def test_service_action_restart(backend, fake_run):
    fake_run(default=res("", 0))
    ok, _ = backend.service_action("wuauserv", "restart")
    assert ok


def test_service_action_enable_disable(backend, fake_run):
    fake_run(default=res("", 0))
    assert backend.service_action("x", "enable")[0] is True
    assert backend.service_action("x", "disable")[0] is True


def test_service_action_errors(backend):
    assert backend.service_action("", "start")[0] is False
    assert backend.service_action("x", "wat")[0] is False


# --------------------------------------------------------------------------- #
#  Пакеты
# --------------------------------------------------------------------------- #
def test_package_manager(backend, monkeypatch):
    monkeypatch.setattr(windows.common, "which",
                        lambda n: "/winget" if n == "winget" else None)
    assert backend.package_manager() == "winget"
    monkeypatch.setattr(windows.common, "which",
                        lambda n: "/choco" if n == "choco" else None)
    assert backend.package_manager() == "choco"
    monkeypatch.setattr(windows.common, "which", lambda n: None)
    assert backend.package_manager() == ""


def test_search_packages(backend, monkeypatch, fake_run):
    monkeypatch.setattr(windows.common, "which", lambda n: "/winget")

    def handler(cmd, **kwargs):
        if "search" in cmd:
            return res("Name  Id  Version\nwget  GNU.Wget  1.0\n")
        if "list" in cmd:
            return res("Name  Id  Version\nwget  GNU.Wget  1.0\n")
        return res("")

    fake_run(handler=handler)
    rows = backend.search_packages("wget")
    assert rows[0]["name"] == "wget"
    assert rows[0]["installed"] is True


def test_search_packages_empty_query(backend):
    assert backend.search_packages("") == []


def test_install_packages_winget(backend, monkeypatch, fake_run):
    monkeypatch.setattr(windows.common, "which",
                        lambda n: "/winget" if n == "winget" else None)
    fake_run(default=res("done", 0))
    ok, out = backend.install_packages(["wget"])
    assert ok and out == "done"
    assert backend.install_packages([])[0] is False


def test_install_packages_choco(backend, monkeypatch, fake_run):
    monkeypatch.setattr(windows.common, "which",
                        lambda n: "/choco" if n == "choco" else None)
    fake_run(default=res("choco-ok", 0))
    ok, out = backend.install_packages(["wget"])
    assert ok and out == "choco-ok"


def test_remove_and_info(backend, monkeypatch, fake_run):
    monkeypatch.setattr(windows.common, "which", lambda n: "/winget")
    fake_run(default=res("info", 0))
    assert backend.remove_packages(["wget"])[0] is True
    assert backend.package_info("wget") == "info"
    assert backend.package_info("") == "Укажи имя пакета"
    assert backend.package_files("x") == windows.NOT_AVAILABLE
    assert backend.file_owner("x") == windows.NOT_AVAILABLE


def test_check_updates(backend, monkeypatch, fake_run):
    monkeypatch.setattr(windows.common, "which", lambda n: "/winget")
    fake_run(default=res("Name  Id  Version  Available\nwget  GNU.Wget  1.0  2.0\n"))
    rows = backend.check_updates()
    assert rows[0] == {"name": "wget", "old": "1.0", "new": "2.0"}


def test_system_update(backend, monkeypatch, fake_run):
    monkeypatch.setattr(windows.common, "which",
                        lambda n: "/winget" if n == "winget" else None)
    fake_run(default=res("upgraded", 0))
    ok, out = backend.system_update()
    assert ok and out == "upgraded"


def test_system_update_none(backend, monkeypatch):
    monkeypatch.setattr(windows.common, "which", lambda n: None)
    assert backend.system_update()[0] is False


# --------------------------------------------------------------------------- #
#  Сеть
# --------------------------------------------------------------------------- #
def test_network_info(backend, fake_run):
    fake_run(default=res("   Host Name . . . : pc\n"))
    info = backend.network_info()
    assert info["hostname"] == "pc"


def test_public_ip(backend, fake_run):
    fake_run(default=res("8.8.4.4"))
    assert backend.public_ip() == "8.8.4.4"


# --------------------------------------------------------------------------- #
#  Датчики и ресурсы
# --------------------------------------------------------------------------- #
def test_sensors_info(backend, fake_run):
    fake_run(default=res("ACPI\\ThermalZone\\TZ00\t3000\n"))
    temps, fans = backend.sensors_info()
    assert temps[0][1] == pytest.approx(3000 / 10.0 - 273.15, abs=0.1)
    assert fans == []


def test_memory_info(backend, fake_run):
    fake_run(default=res("16777216 8388608"))
    total, used = backend.memory_info()
    assert total == 16.0
    assert used == 8.0


def test_cpu_percent_uptime_model(backend, fake_run):
    fake_run(default=res("42"))
    assert backend.cpu_percent() == 42.0
    fake_run(default=res("90061"))
    assert backend.uptime() == "1 д 1 ч 1 мин"
    fake_run(default=res("AMD Ryzen 5"))
    assert backend.cpu_model() == "AMD Ryzen 5"


def test_battery_info(backend, fake_run):
    fake_run(default=res("BAT0\t80\t2"))
    info = backend.battery_info()
    assert info["capacity"] == "80"
    assert info["status"] == "Подключён к сети"


def test_battery_info_none(backend, fake_run):
    fake_run(default=res(""))
    assert backend.battery_info() is None


# --------------------------------------------------------------------------- #
#  Автозапуск
# --------------------------------------------------------------------------- #
def test_list_startup(backend, fake_run):
    out = ("R\tOneDrive\tC:\\OneDrive.exe\t"
           "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\n"
           "F\tsync.lnk\tC:\\Startup\\sync.lnk\tC:\\Startup\n"
           "F\told.disabled\tC:\\Startup\\old.disabled\tC:\\Startup\n")
    fake_run(default=res(out))
    rows = backend.list_startup()
    assert rows[0]["source"] == "реестр (HKCU)"
    assert rows[1]["enabled"] is True
    assert rows[2]["enabled"] is False


def test_set_startup_enabled_file(backend, tmp_path):
    path = tmp_path / "app.lnk"
    path.write_text("x")
    entry = {"path": str(path), "source": "папка «Автозагрузка»"}
    assert backend.set_startup_enabled(entry, False) is True
    disabled = tmp_path / "app.lnk.disabled"
    assert disabled.exists()
    # включение обратно идёт уже по переименованному пути
    assert backend.set_startup_enabled({"path": str(disabled),
                                        "source": "папка «Автозагрузка»"},
                                       True) is True
    assert path.exists()


def test_set_startup_enabled_registry(backend):
    entry = {"path": "HKCU\\...\\x", "source": "реестр (HKCU)"}
    assert backend.set_startup_enabled(entry, True) is False
    assert backend.set_startup_enabled({}, True) is False


# --------------------------------------------------------------------------- #
#  Диск и железо
# --------------------------------------------------------------------------- #
def test_mounts(backend, fake_run):
    fake_run(default=res("D\tC\tC:\\\t100\t200\tNTFS\n"))
    rows = backend.mounts()
    assert rows[0]["target"] == "C:\\"
    assert rows[0]["fstype"] == "NTFS"


def test_disks_overview(backend, fake_run):
    fake_run(default=res("=== LOGICAL ===\nC: NTFS\n=== PHYSICAL ===\nDisk0\n"))
    text = backend.disks_overview()
    assert "Логические диски:" in text
    assert "Физические диски:" in text


def test_disks_overview_empty(backend, fake_run):
    fake_run(default=res(""))
    assert "Не удалось" in backend.disks_overview()


def test_smart_health(backend, fake_run):
    fake_run(default=res("counter"))
    assert backend.smart_health() == "counter"
    fake_run(default=res(""))
    assert "SMART" in backend.smart_health()


def test_hardware_sections(backend, fake_run, monkeypatch):
    out = ("###CPU###\nRyzen\n###GPU###\nRadeon\n###RAM###\n16GB\n###BOARD###\nB450\n")
    fake_run(default=res(out))
    monkeypatch.setattr(backend, "memory_info", lambda: (16.0, 8.0))
    titles = [t for t, _ in backend.hardware_sections()]
    assert titles == ["Процессор", "Видеокарта(ы)", "Оперативная память",
                      "Материнская плата", "Память"]


def test_diagnostics(backend, fake_run):
    fake_run(default=res("event log\nSTOPPED\t3"))
    out = dict(backend.diagnostics())
    assert out["Службы не запущены"] == "3"


def test_boot_analysis(backend, fake_run):
    fake_run(default=res("Загрузка: now\n---\nanalysis"))
    out = dict(backend.boot_analysis())
    assert "Загрузка" in out


def test_boot_analysis_empty(backend, fake_run):
    fake_run(default=res(""))
    assert backend.boot_analysis()[0][1] == windows.NOT_AVAILABLE


def test_list_timers_raw(backend, fake_run):
    fake_run(default=res("TaskName: x"))
    assert backend.list_timers_raw() == "TaskName: x"
    fake_run(default=res(""))
    assert "не найдены" in backend.list_timers_raw()


def test_list_modules(backend, fake_run):
    fake_run(default=res("ntfs\t100\tRunning\tC:\\ntfs.sys\n"))
    rows = backend.list_modules()
    assert rows[0]["name"] == "ntfs"
    assert rows[0]["used"] == "Running"


def test_module_action_unsupported(backend):
    ok, msg = backend.module_action("ntfs", "load")
    assert ok is False and "не поддерживается" in msg


def test_firewall_and_journal(backend, fake_run):
    fake_run(default=res("Domain True"))
    assert backend.firewall_status() == "Domain True"
    assert backend.firewall_status_root() == "Domain True"
    fake_run(default=res("log"))
    assert backend.journal_entries("err", 10) == "log"


# --------------------------------------------------------------------------- #
#  Порты
# --------------------------------------------------------------------------- #
def test_listening_ports(backend, fake_run):
    out = ("  TCP    0.0.0.0:135    0.0.0.0:0    LISTENING    900\n"
           "  UDP    0.0.0.0:500    0.0.0.0:0    500\n")
    fake_run(default=res(out))
    rows = backend.listening_ports()
    assert rows[0]["local"] == "0.0.0.0:135"
    assert rows[0]["proc"] == "900"


def test_established_connections(backend, fake_run):
    out = "  TCP    10.0.0.1:5000    1.1.1.1:443    ESTABLISHED    1234\n"
    fake_run(default=res(out))
    rows = backend.established_connections()
    assert rows[0]["peer"] == "1.1.1.1:443"


# --------------------------------------------------------------------------- #
#  Твики и корзина
# --------------------------------------------------------------------------- #
def test_tweaks(backend, monkeypatch):
    assert backend.get_swappiness() == 60
    assert backend.set_swappiness(10) is False
    monkeypatch.setattr(windows.common, "run_out",
                        lambda cmd, **k: "Power scheme GUID: 381b (Balanced)")
    assert backend.cpu_governor() == "Balanced"
    assert backend.cpu_governors() == []
    assert backend.set_cpu_governor("x") is False
    assert "Windows" in backend.thp_status()
    assert backend.trash_items() == []


def test_empty_trash(backend, fake_run):
    fake_run(default=res("", 0))
    assert backend.empty_trash()[0] is True
    fake_run(default=res("", 1))
    assert backend.empty_trash()[0] is False
