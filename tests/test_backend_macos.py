"""Юнит-тесты macOS-бэкенда (``skaycleartux.backends.macos``).

Проверяем разбор вывода утилит macOS и корректную деградацию там, где
Homebrew или утилита недоступны. Реальная система не затрагивается.
"""
from __future__ import annotations

import subprocess

import pytest

from skaycleartux.backends import macos
from skaycleartux.backends.macos import MacOSBackend, _plist_label


def res(stdout="", code=0):
    return subprocess.CompletedProcess([], code, stdout, "")


@pytest.fixture
def backend():
    return MacOSBackend()


def test_list_processes_sorted(backend, fake_run):
    out = ("  10 user 1.0 0.1 100 aaa cmd-a\n"
           "  20 user 9.0 0.1 200 bbb cmd-b\n")
    fake_run(default=res(out))
    rows = backend.list_processes()
    assert [r["pid"] for r in rows] == [20, 10]


def test_kill_process_ok(backend, monkeypatch):
    monkeypatch.setattr(macos.os, "kill", lambda pid, sig: None)
    assert backend.kill_process(5)[0] is True


def test_kill_process_gone(backend, monkeypatch):
    def boom(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(macos.os, "kill", boom)
    ok, msg = backend.kill_process(5)
    assert ok is False and "завершён" in msg


def test_kill_process_permission(backend, monkeypatch, fake_run):
    def boom(pid, sig):
        raise PermissionError()

    monkeypatch.setattr(macos.os, "kill", boom)
    fake_run(default=res("", 0))
    ok, msg = backend.kill_process(5)
    assert ok and "администратора" in msg


def test_list_services(backend, fake_run):
    out = "PID\tStatus\tLabel\n123\t0\tcom.apple.foo\n-\t0\tcom.apple.bar\n"
    fake_run(default=res(out))
    rows = backend.list_services()
    assert rows[0]["unit"] == "com.apple.foo"
    assert rows[0]["active"] == "running"
    assert rows[1]["active"] == "loaded"


def test_service_action_empty(backend):
    ok, msg = backend.service_action("", "start")
    assert ok is False and "имя службы" in msg


def test_service_action_unsupported(backend):
    ok, msg = backend.service_action("com.x", "explode")
    assert ok is False and "не поддерживается" in msg


def test_service_action_start(backend, fake_run):
    fake_run(default=res("", 0))
    ok, msg = backend.service_action("com.x", "start")
    assert ok and "запущена" in msg


def test_package_manager(backend, monkeypatch):
    monkeypatch.setattr(macos.common, "which",
                        lambda n: "/opt/homebrew/bin/brew" if n == "brew" else None)
    assert backend.package_manager() == "brew"


def test_package_manager_absent(backend, monkeypatch):
    monkeypatch.setattr(macos.common, "which", lambda n: None)
    assert backend.package_manager() == ""


def test_search_packages(backend, monkeypatch, fake_run):
    monkeypatch.setattr(macos.common, "which", lambda n: "/usr/local/bin/brew")

    def handler(cmd, **kwargs):
        if cmd[:2] == ["brew", "search"]:
            return res("==> Formulae\nwget 1.21\ncurl 8.0\n")
        if cmd[:2] == ["brew", "list"]:
            return res("wget\n")
        return res("")

    fake_run(handler=handler)
    rows = backend.search_packages("w")
    assert rows[0]["name"] == "wget"
    assert rows[0]["installed"] is True
    assert rows[1]["installed"] is False


def test_install_remove_no_brew(backend, monkeypatch):
    monkeypatch.setattr(macos.common, "which", lambda n: None)
    assert backend.install_packages(["x"])[0] is False
    assert backend.remove_packages(["x"])[0] is False
    assert backend.install_packages([])[0] is False


def test_install_packages(backend, monkeypatch, fake_run):
    monkeypatch.setattr(macos.common, "which", lambda n: "/brew")
    fake_run(default=res("installed", 0))
    ok, out = backend.install_packages(["wget"])
    assert ok and "installed" in out


def test_package_files_and_info(backend, monkeypatch):
    monkeypatch.setattr(macos.common, "which", lambda n: "/brew")
    monkeypatch.setattr(macos.common, "run_out", lambda cmd, **k: "data")
    assert backend.package_files("wget") == "data"
    assert backend.package_info("wget") == "data"
    assert backend.package_files("") == "Укажи имя пакета"


def test_file_owner(backend, monkeypatch):
    monkeypatch.setattr(macos.common, "run_out",
                        lambda cmd, **k: "owner" if cmd[0] == "pkgutil" else "")
    assert backend.file_owner("/usr/bin/x") == "owner"
    assert backend.file_owner("") == "Укажи путь к файлу"


def test_check_updates(backend, monkeypatch, fake_run):
    monkeypatch.setattr(macos.common, "which", lambda n: "/brew")
    fake_run(default=res("==> Outdated\nwget (1.0) < 2.0\ncurl 8.1\n"))
    rows = backend.check_updates()
    assert rows[0] == {"name": "wget", "old": "1.0", "new": "2.0"}
    assert rows[1]["name"] == "curl"


def test_check_updates_no_brew(backend, monkeypatch):
    monkeypatch.setattr(macos.common, "which", lambda n: None)
    assert backend.check_updates() == []


def test_system_update(backend, monkeypatch, fake_run):
    monkeypatch.setattr(macos.common, "which", lambda n: "/brew")
    fake_run(default=res("upgraded", 0))
    ok, out = backend.system_update()
    assert ok and out == "upgraded"


def test_network_info(backend, monkeypatch, fake_run):
    ifconfig = (
        "en0: flags=8863<UP,BROADCAST> mtu 1500\n"
        "\tinet 192.168.1.10 netmask 0xffffff00\n"
        "\tether aa:bb:cc:dd:ee:ff\n"
        "lo0: flags=8049<UP,LOOPBACK>\n"
        "\tinet 127.0.0.1 netmask 0xff000000\n"
    )

    def handler(cmd, **kwargs):
        if cmd[0] == "ifconfig":
            return res(ifconfig)
        if cmd[:3] == ["route", "-n", "get"]:
            return res("gateway: 192.168.1.1\ninterface: en0\n")
        if cmd[0] == "scutil":
            return res("nameserver[0] : 1.1.1.1\nnameserver[1] : 8.8.8.8\n")
        return res("")

    fake_run(handler=handler)
    monkeypatch.setattr(macos.os, "uname",
                        lambda: type("U", (), {"nodename": "mac"})())
    info = backend.network_info()
    assert info["hostname"] == "mac"
    assert info["interfaces"][0]["mac"] == "aa:bb:cc:dd:ee:ff"
    assert info["interfaces"][0]["state"] == "UP"
    assert "192.168.1.1" in info["route"]
    assert info["dns"] == ["1.1.1.1", "8.8.8.8"]


def test_default_route_fallback(backend, monkeypatch):
    monkeypatch.setattr(macos.common, "run_out",
                        lambda cmd, **k: "" if cmd[0] == "route"
                        else "default 192.168.0.1 UGSc en0")
    assert "default 192.168.0.1" in backend._default_route()


def test_sensors_info(backend, monkeypatch):
    monkeypatch.setattr(macos.common, "which",
                        lambda n: "/usr/local/bin/osx-cpu-temp" if n == "osx-cpu-temp" else None)
    monkeypatch.setattr(macos.common, "run_out",
                        lambda cmd, **k: "CPU: 55.0C\n" if cmd[0].endswith("osx-cpu-temp")
                        else '"F0Ac" = 2000')
    temps, fans = backend.sensors_info()
    assert temps[0][1] == 55.0
    assert fans and fans[0][1] == 2000.0


def test_memory_info(backend, monkeypatch, fake_run):
    def handler(cmd, **kwargs):
        if cmd[:2] == ["sysctl", "-n"]:
            return res("17179869184")  # 16 GiB
        if cmd[0] == "vm_stat":
            return res("page size of 4096 bytes\nPages free: 1000.\nPages inactive: 2000.\n")
        return res("")

    fake_run(handler=handler)
    total, used = backend.memory_info()
    assert total == 16.0
    assert used >= 0


def test_cpu_percent(backend, fake_run, monkeypatch):
    fake_run(default=res("%CPU\n50.0\n50.0\n"))
    monkeypatch.setattr(macos.os, "cpu_count", lambda: 2)
    assert backend.cpu_percent() == 50.0


def test_uptime(backend, monkeypatch):
    monkeypatch.setattr(macos.common, "run_out",
                        lambda cmd, **k: "{ sec = 1600000000, usec = 0 }")
    assert backend.uptime().endswith("мин")


def test_cpu_model(backend, monkeypatch):
    monkeypatch.setattr(macos.common, "run_out",
                        lambda cmd, **k: "Apple M2")
    assert backend.cpu_model() == "Apple M2"


def test_battery_info_none(backend, fake_run):
    fake_run(default=res("No battery"))
    assert backend.battery_info() is None


def test_battery_info(backend, monkeypatch, fake_run):
    def handler(cmd, **kwargs):
        if cmd[0] == "pmset":
            return res("Now drawing from 'Battery Power'\n -InternalBattery-0 75%; discharging;")
        if cmd[0] == "ioreg":
            return res('"MaxCapacity" = 90\n"DesignCapacity" = 100\n"CurrentCapacity" = 68\n')
        return res("")

    fake_run(handler=handler)
    info = backend.battery_info()
    assert info["capacity"] == "75"
    assert info["status"] == "Discharging"
    assert info["health"] == "90%"


def test_plist_label(tmp_path):
    p = tmp_path / "a.plist"
    p.write_text("<key>Label</key>\n<string>com.example.app</string>\n")
    assert _plist_label(p) == "com.example.app"
    assert _plist_label(tmp_path / "missing.plist") == ""


def test_list_startup(backend, monkeypatch, tmp_path):
    user = tmp_path / "LaunchAgents"
    user.mkdir()
    (user / "a.plist").write_text("<key>Label</key><string>com.a</string>")
    monkeypatch.setattr(macos, "LAUNCH_AGENTS_USER", user)
    monkeypatch.setattr(macos, "LAUNCH_AGENTS_SYSTEM", tmp_path / "none")
    rows = backend.list_startup()
    assert rows[0]["name"] == "com.a"
    assert rows[0]["source"] == "пользователь"


def test_set_startup_enabled(backend, fake_run):
    fake_run(default=res("", 0))
    entry = {"path": "/tmp/a.plist", "source": "пользователь"}
    assert backend.set_startup_enabled(entry, True) is True
    assert backend.set_startup_enabled({}, True) is False


def test_mounts(backend, fake_run):
    out = "/dev/disk1s1 on / (apfs, local, journaled)\n"
    fake_run(default=res(out))
    rows = backend.mounts()
    assert rows[0]["src"] == "/dev/disk1s1"
    assert rows[0]["fstype"] == "apfs"


def test_disks_overview(backend, monkeypatch):
    monkeypatch.setattr(macos.common, "run_out", lambda cmd, **k: "disk")
    assert "Устройства:" in backend.disks_overview()


def test_smart_health(backend, monkeypatch):
    def run_out(cmd, **k):
        if cmd[:2] == ["diskutil", "list"]:
            return "/dev/disk0\n/dev/disk1"
        return "SMART status: Verified"
    monkeypatch.setattr(macos.common, "run_out", run_out)
    assert "SMART status: Verified" in backend.smart_health()


def test_hardware_sections(backend, monkeypatch):
    monkeypatch.setattr(macos.common, "run_out",
                        lambda cmd, **k: "hw" if cmd[0] == "system_profiler" else "")
    monkeypatch.setattr(backend, "memory_info", lambda: (16.0, 8.0))
    titles = [t for t, _ in backend.hardware_sections()]
    assert "Оборудование" in titles and "Память" in titles


def test_diagnostics(backend, monkeypatch):
    monkeypatch.setattr(macos.common, "run_out", lambda cmd, **k: "err")
    monkeypatch.setattr(backend, "disk_usage", lambda p=None: (100, 50, 50))
    monkeypatch.setattr(backend, "firewall_status", lambda: "fw")
    titles = [t for t, _ in backend.diagnostics()]
    assert "Файрвол" in titles


def test_boot_analysis(backend, monkeypatch):
    monkeypatch.setattr(macos.common, "run_out",
                        lambda cmd, **k: "{ sec = 1600000000 }")
    monkeypatch.setattr(backend, "list_startup", lambda: [])
    assert backend.boot_analysis()


def test_list_timers_raw(backend):
    assert "launchd" in backend.list_timers_raw()


def test_modules_unsupported(backend):
    assert backend.list_modules() == []
    ok, msg = backend.module_action("x", "load")
    assert ok is False and "kext" in msg


def test_firewall_status(backend, monkeypatch):
    monkeypatch.setattr(macos.os.path, "exists", lambda p: False)
    monkeypatch.setattr(macos.common, "run_out", lambda cmd, **k: "")
    assert "недоступен" in backend.firewall_status()


def test_journal_entries(backend, monkeypatch):
    monkeypatch.setattr(macos.common, "run", lambda cmd, **k: res("log line"))
    assert backend.journal_entries("err", 10) == "log line"


def test_listening_ports(backend, fake_run):
    out = ("COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
           "sshd 1 root 3u IPv4 0 0t0 TCP *:22 (LISTEN)\n")
    fake_run(default=res(out))
    rows = backend.listening_ports()
    assert rows[0]["local"] == "*:22"
    assert rows[0]["proc"] == "sshd(1)"


def test_established_connections(backend, fake_run):
    out = ("COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
           "curl 9 u 3u IPv4 0 0t0 TCP 10.0.0.1:5000->1.1.1.1:443 (ESTABLISHED)\n")
    fake_run(default=res(out))
    rows = backend.established_connections()
    assert rows[0]["peer"] == "1.1.1.1:443"


def test_tweaks(backend, monkeypatch):
    assert backend.get_swappiness() == 60
    assert backend.set_swappiness(10) is False
    monkeypatch.setattr(macos.common, "run_out", lambda cmd, **k: "powermode 1")
    assert "powermode" in backend.cpu_governor()
    assert backend.cpu_governors() == []
    assert backend.set_cpu_governor("x") is False
    assert "macOS" in backend.thp_status()
    assert "macOS" in backend.zram_status()


def test_trash_items_and_empty(backend, monkeypatch, tmp_path):
    monkeypatch.setattr(macos.Path, "home",
                        classmethod(lambda cls: tmp_path))
    trash = tmp_path / ".Trash"
    trash.mkdir()
    (trash / "file.txt").write_text("data")
    items = backend.trash_items()
    assert items and items[0]["name"] == "file.txt"
    ok, msg = backend.empty_trash()
    assert ok and "очищена" in msg
