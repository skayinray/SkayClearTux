"""Юнит-тесты Linux-бэкенда (``skaycleartux.backends.linux``).

Все вызовы подпроцессов подменяются, файлы /proc и /sys — тоже, поэтому
тесты идут на любой ОС и не трогают реальную систему.
"""
from __future__ import annotations
import sys

import subprocess
from pathlib import Path

import pytest

from skaycleartux.backends import linux, linux_pkg
from skaycleartux.backends.linux import LinuxBackend, _parse_desktop

PS_OUT = (
    "  123 root      12.5  1.2 20480 systemd /sbin/init splash\n"
    "  456 tima       3.0  0.5  4096 firefox /usr/lib/firefox\n"
    "bad line\n"
)


@pytest.fixture
def backend():
    return LinuxBackend()


def test_list_processes(backend, fake_run):
    fake_run(default=common_result(PS_OUT))
    rows = backend.list_processes()
    assert [r["pid"] for r in rows] == [123, 456]
    assert rows[0]["name"] == "systemd"
    assert rows[1]["cpu"] == 3.0


def common_result(stdout="", returncode=0, cmd=None):
    return subprocess.CompletedProcess(cmd or [], returncode, stdout, "")


# --------------------------------------------------------------------------- #
#  Процессы
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(sys.platform == "win32", reason="Unix only")
def test_kill_process_ok(backend, monkeypatch):
    monkeypatch.setattr(linux.os, "kill", lambda pid, sig: None)
    ok, msg = backend.kill_process(42, force=True)
    assert ok and "SIGKILL" in msg


def test_kill_process_already_gone(backend, monkeypatch):
    def boom(pid, sig):
        raise ProcessLookupError()

    monkeypatch.setattr(linux.os, "kill", boom)
    ok, msg = backend.kill_process(42)
    assert ok is False and "завершён" in msg


def test_kill_process_permission_escalates(backend, monkeypatch, fake_run):
    def boom(pid, sig):
        raise PermissionError()

    monkeypatch.setattr(linux.os, "kill", boom)
    fake_run(default=common_result("", 0))
    ok, msg = backend.kill_process(42)
    assert ok and "pkexec" in msg


def test_kill_process_permission_denied(backend, monkeypatch, fake_run):
    def boom(pid, sig):
        raise PermissionError()

    monkeypatch.setattr(linux.os, "kill", boom)
    fake_run(default=common_result("", 1))
    ok, msg = backend.kill_process(42)
    assert ok is False and "root" in msg


# --------------------------------------------------------------------------- #
#  Службы
# --------------------------------------------------------------------------- #
def test_list_services(backend, fake_run):
    out = ("ssh.service loaded active running OpenSSH server\n"
           "● foo.service loaded failed failed Broken unit\n"
           "short line\n"
           "gone.service not-found inactive dead Gone\n")
    fake_run(default=common_result(out))
    rows = backend.list_services()
    units = [r["unit"] for r in rows]
    assert "ssh.service" in units
    assert "foo.service" in units
    assert "gone.service" not in units
    assert rows[0]["active"] == "active"


def test_service_action(backend, fake_run):
    fake_run(default=common_result("", 0))
    ok, msg = backend.service_action("ssh.service", "restart")
    assert ok and "systemctl restart ssh.service" in msg


# --------------------------------------------------------------------------- #
#  Пакеты (делегирование в linux_pkg)
# --------------------------------------------------------------------------- #
def test_package_methods_delegate(backend, monkeypatch):
    calls = {}

    class FakeMgr:
        key = "fake"
        title = "Fake"

        def search(self, q):
            calls["search"] = q
            return [{"name": q}]

        def install(self, names):
            return True, "installed"

        def remove(self, names):
            return True, "removed"

        def files(self, pkg):
            return "files"

        def owner(self, path):
            return "owner"

        def info(self, pkg):
            return "info"

        def updates(self):
            return [{"name": "x"}]

        def upgrade(self):
            return True, "upgraded"

    monkeypatch.setattr(linux_pkg, "detect", lambda *a, **k: FakeMgr())
    assert backend.package_manager() == "fake"
    assert backend.search_packages("vim") == [{"name": "vim"}]
    assert calls["search"] == "vim"
    assert backend.install_packages(["vim"]) == (True, "installed")
    assert backend.remove_packages(["vim"]) == (True, "removed")
    assert backend.package_files("vim") == "files"
    assert backend.file_owner("/bin/vim") == "owner"
    assert backend.package_info("vim") == "info"
    assert backend.check_updates() == [{"name": "x"}]
    assert backend.system_update() == (True, "upgraded")


# --------------------------------------------------------------------------- #
#  Сеть
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(sys.platform == "win32", reason="Unix only")
def test_network_info(backend, monkeypatch, fake_run):
    def handler(cmd, **kwargs):
        if cmd[:3] == ["ip", "-brief", "addr"]:
            return common_result("eth0 UP 192.168.1.5/24\nlo UNKNOWN 127.0.0.1/8\n")
        if cmd[:3] == ["ip", "route", "show"]:
            return common_result("default via 192.168.1.1 dev eth0")
        return common_result("")

    fake_run(handler=handler)
    monkeypatch.setattr(linux.common, "read_text", lambda p: "aa:bb:cc:dd:ee:ff")
    monkeypatch.setattr(linux.Path, "read_text",
                        lambda self, *a, **k: "nameserver 1.1.1.1\n")
    monkeypatch.setattr(linux.os, "uname",
                        lambda: type("U", (), {"nodename": "host"})())
    info = backend.network_info()
    assert info["hostname"] == "host"
    assert info["interfaces"][0]["name"] == "eth0"
    assert info["dns"] == ["1.1.1.1"]
    assert "default" in info["route"]


# --------------------------------------------------------------------------- #
#  Датчики и ресурсы
# --------------------------------------------------------------------------- #
def test_sensors_info_from_sensors(backend, monkeypatch, fake_run):
    payload = '{"coretemp-isa-0000": {"Package id 0": {"temp1_input": 45.0},'
    payload += ' "fan1": {"fan1_input": 1200.0}}}'
    monkeypatch.setattr(linux.shutil, "which", lambda n: "/usr/bin/sensors")
    fake_run(default=common_result(payload))
    temps, fans = backend.sensors_info()
    assert temps and temps[0][1] == 45.0
    assert fans and fans[0][1] == 1200.0


def test_sensors_info_fallback_thermal(backend, monkeypatch, fake_run, tmp_path):
    monkeypatch.setattr(linux.shutil, "which", lambda n: None)
    fake_run(default=common_result(""))
    zone = tmp_path / "thermal_zone0"
    zone.mkdir()
    (zone / "temp").write_text("45000")
    (zone / "type").write_text("acpitz")
    monkeypatch.setattr(linux.Path, "glob", lambda self, pat: [zone])
    monkeypatch.setattr(linux.common, "read_text",
                        lambda p: Path(p).read_text())
    temps, fans = backend.sensors_info()
    assert temps and temps[0][1] == 45.0


def test_memory_info(backend, monkeypatch):
    text = "MemTotal:       8000000 kB\nMemAvailable:   3000000 kB\n"
    monkeypatch.setattr(linux.Path, "read_text",
                        lambda self, *a, **k: text)
    total, used = backend.memory_info()
    assert round(total, 1) == 7.6
    assert round(used, 1) == 4.8


def test_memory_info_error(backend, monkeypatch):
    monkeypatch.setattr(linux.Path, "read_text",
                        lambda self, *a, **k: (_ for _ in ()).throw(OSError()))
    assert backend.memory_info() == (0.0, 0.0)


def test_load_avg(backend, monkeypatch):
    monkeypatch.setattr(linux.Path, "read_text",
                        lambda self, *a, **k: "0.5 0.25 0.1 1/100 999")
    assert backend.load_avg() == (0.5, 0.25, 0.1)


def test_cpu_percent(backend, monkeypatch):
    seq = iter(["cpu 100 0 100 800 0 0 0 0", "cpu 200 0 200 1400 0 0 0 0"])

    def read(self, *a, **k):
        return next(seq)

    monkeypatch.setattr(linux.Path, "read_text", read)
    assert backend.cpu_percent() == 0.0  # первый вызов — базовая точка
    assert backend.cpu_percent() == 25.0


def test_uptime(backend, monkeypatch):
    monkeypatch.setattr(linux.Path, "read_text",
                        lambda self, *a, **k: "90061.0 100.0")
    assert backend.uptime() == "1 д 1 ч 1 мин"


def test_cpu_model(backend, monkeypatch):
    monkeypatch.setattr(linux.common, "read_text",
                        lambda p: "processor: 0\nmodel name\t: AMD Ryzen\n")
    assert backend.cpu_model() == "AMD Ryzen"


def test_battery_info_none(backend, monkeypatch):
    monkeypatch.setattr(linux.Path, "glob", lambda self, pat: [])
    assert backend.battery_info() is None


def test_battery_info(backend, monkeypatch, tmp_path):
    bat = tmp_path / "BAT0"
    bat.mkdir()
    (bat / "capacity").write_text("80")
    (bat / "status").write_text("Discharging")
    (bat / "health").write_text("Good")
    monkeypatch.setattr(linux.Path, "glob", lambda self, pat: [bat])
    monkeypatch.setattr(linux.common, "read_text",
                        lambda p: Path(p).read_text() if Path(p).exists() else "")
    info = backend.battery_info()
    assert info["name"] == "BAT0"
    assert info["capacity"] == "80"


# --------------------------------------------------------------------------- #
#  Автозапуск
# --------------------------------------------------------------------------- #
def test_parse_desktop(tmp_path):
    p = tmp_path / "app.desktop"
    p.write_text("# comment\n[Desktop Entry]\nName=App\nExec=app --run\n")
    data = _parse_desktop(p)
    assert data["Name"] == "App"
    assert data["Exec"] == "app --run"


def test_parse_desktop_missing(tmp_path):
    assert _parse_desktop(tmp_path / "no.desktop") is None


def test_list_startup(backend, monkeypatch, tmp_path):
    user = tmp_path / "user"
    user.mkdir()
    (user / "app.desktop").write_text(
        "[Desktop Entry]\nName=MyApp\nExec=myapp\nHidden=true\n")
    monkeypatch.setattr(linux, "AUTOSTART_USER", user)
    monkeypatch.setattr(linux, "AUTOSTART_SYSTEM", tmp_path / "sys")
    rows = backend.list_startup()
    assert rows[0]["name"] == "MyApp"
    assert rows[0]["enabled"] is False
    assert rows[0]["source"] == "пользователь"


def test_set_startup_enabled_user(backend, monkeypatch, tmp_path):
    user = tmp_path / "user"
    user.mkdir()
    src = tmp_path / "app.desktop"
    src.write_text("[Desktop Entry]\nName=MyApp\nExec=myapp\n")
    monkeypatch.setattr(linux, "AUTOSTART_USER", user)
    entry = {"name": "MyApp", "exec": "myapp", "enabled": True,
             "source": "пользователь", "path": src}
    assert backend.set_startup_enabled(entry, False) is True
    written = (user / "app.desktop").read_text()
    assert "Hidden=true" in written


# --------------------------------------------------------------------------- #
#  Диск и железо
# --------------------------------------------------------------------------- #
def test_mounts(backend, monkeypatch):
    text = ("proc /proc proc rw 0 0\n"
            "/dev/sda1 / ext4 rw,relatime 0 0\n")
    monkeypatch.setattr(linux.Path, "read_text", lambda self, *a, **k: text)
    rows = backend.mounts()
    assert rows == [{"src": "/dev/sda1", "target": "/", "fstype": "ext4",
                     "opts": "rw,relatime"}]


def test_disks_overview(backend, monkeypatch):
    monkeypatch.setattr(linux.common, "run_out",
                        lambda cmd, **k: "output-" + cmd[0])
    text = backend.disks_overview()
    assert "Устройства:" in text
    assert "Использование файловых систем:" in text


def test_smart_health_not_installed(backend, monkeypatch):
    monkeypatch.setattr(linux.shutil, "which", lambda n: None)
    assert "smartctl не установлен" in backend.smart_health()


def test_smart_health_devices(backend, monkeypatch):
    monkeypatch.setattr(linux.shutil, "which", lambda n: "/usr/sbin/smartctl")
    monkeypatch.setattr(linux.Path, "glob",
                        lambda self, pat: [Path("/dev/sda")])
    monkeypatch.setattr(linux.common, "run_out", lambda cmd, **k: "SMART OK")
    text = backend.smart_health()
    assert "SMART OK" in text


def test_hardware_sections(backend, monkeypatch):
    monkeypatch.setattr(linux.common, "run_out",
                        lambda cmd, **k: "info" if cmd[0] != "lsblk" else "")
    monkeypatch.setattr(backend, "memory_info", lambda: (16.0, 4.0))
    sections = backend.hardware_sections()
    titles = [t for t, _ in sections]
    assert "Процессор" in titles
    assert "Память" in titles


def test_diagnostics(backend, monkeypatch):
    monkeypatch.setattr(linux.common, "run_out", lambda cmd, **k: "err")
    monkeypatch.setattr(linux.Path, "exists", lambda self: False)
    titles = [t for t, _ in backend.diagnostics()]
    assert "Упавшие службы" in titles


def test_boot_analysis(backend, monkeypatch):
    monkeypatch.setattr(linux.common, "run_out", lambda cmd, **k: "blame")
    assert len(backend.boot_analysis()) == 3


def test_list_timers_raw_empty(backend, monkeypatch):
    monkeypatch.setattr(linux.common, "run_out", lambda cmd, **k: "")
    assert backend.list_timers_raw() == "Активных таймеров нет"


def test_list_modules(backend, fake_run):
    out = "Module Size Used by\nnvidia 100 2 drm\nusbhid 50 0\n"
    fake_run(default=common_result(out))
    rows = backend.list_modules()
    assert rows[0]["name"] == "nvidia"
    assert rows[0]["by"] == "drm"


def test_module_action(backend, fake_run):
    fake_run(default=common_result("", 0))
    ok, msg = backend.module_action("nvidia", "load")
    assert ok and "загружен" in msg


# --------------------------------------------------------------------------- #
#  Файрвол, журнал, порты
# --------------------------------------------------------------------------- #
def test_firewall_status(backend, monkeypatch):
    monkeypatch.setattr(linux.shutil, "which", lambda n: None)
    monkeypatch.setattr(linux.common, "run_out", lambda cmd, **k: "")
    assert "не найдены" in backend.firewall_status()


def test_firewall_status_root(backend, monkeypatch):
    monkeypatch.setattr(linux.shutil, "which",
                        lambda n: "/usr/sbin/ufw" if n == "ufw" else None)
    monkeypatch.setattr(linux.common, "run_out", lambda cmd, **k: "Status: active")
    assert "active" in backend.firewall_status_root()


def test_journal_entries(backend, monkeypatch):
    monkeypatch.setattr(linux.common, "run_out", lambda cmd, **k: "log line")
    assert backend.journal_entries("err", 10, "ssh.service") == "log line"


def test_journal_entries_empty(backend, monkeypatch):
    monkeypatch.setattr(linux.common, "run_out", lambda cmd, **k: "")
    assert backend.journal_entries() == "Записей нет"


def test_listening_ports(backend, fake_run):
    out = ("Netid State  Recv-Q Send-Q Local\n"
           "tcp   LISTEN 0      128    0.0.0.0:22   users:((\"sshd\",pid=1,fd=3))\n")
    fake_run(default=common_result(out))
    rows = backend.listening_ports()
    assert rows[0]["proto"] == "tcp"
    assert rows[0]["local"] == "0.0.0.0:22"


def test_established_connections(backend, fake_run):
    out = ("Netid State Recv-Q Send-Q Local Address:Port Peer Address:Port\n"
           "tcp   ESTAB 0      0      10.0.0.1:5000      1.1.1.1:443 users:((\"x\",pid=2))\n")
    fake_run(default=common_result(out))
    rows = backend.established_connections()
    assert rows and rows[0]["local"] == "10.0.0.1:5000"


# --------------------------------------------------------------------------- #
#  Твики
# --------------------------------------------------------------------------- #
def test_get_swappiness(backend, monkeypatch):
    monkeypatch.setattr(linux.common, "read_text", lambda p: "10")
    assert backend.get_swappiness() == 10


def test_get_swappiness_bad(backend, monkeypatch):
    monkeypatch.setattr(linux.common, "read_text", lambda p: "not-a-number")
    assert backend.get_swappiness() == 60


def test_set_swappiness(backend, fake_run):
    fake_run(default=common_result("", 0))
    assert backend.set_swappiness(10) is True


def test_cpu_governor(backend, monkeypatch):
    monkeypatch.setattr(linux.common, "read_text", lambda p: "powersave")
    assert backend.cpu_governor() == "powersave"


def test_cpu_governors(backend, monkeypatch):
    monkeypatch.setattr(linux.common, "read_text",
                        lambda p: "performance powersave")
    assert backend.cpu_governors() == ["performance", "powersave"]


def test_set_cpu_governor_rejects_injection(backend):
    # значение с пробелом/`;` не должно попасть в команду
    assert backend.set_cpu_governor("performance; rm -rf /") is False
    assert backend.set_cpu_governor("$(whoami)") is False


def test_set_cpu_governor_valid(backend, monkeypatch, fake_run):
    monkeypatch.setattr(linux.common, "read_text", lambda p: "performance powersave")
    monkeypatch.setattr(linux.Path, "glob",
                        lambda self, pat: [Path("/sys/.../scaling_governor")])
    runner = fake_run(default=common_result("", 0))
    assert backend.set_cpu_governor("powersave") is True
    # ни одного shell-вызова: только tee с путём и значение через stdin
    assert all(cmd[0] == "tee" for cmd in runner.commands())
    assert runner.kwargs[0]["input_text"] == "powersave\n"


def test_set_cpu_governor_unknown(backend, monkeypatch):
    monkeypatch.setattr(linux.common, "read_text", lambda p: "performance")
    assert backend.set_cpu_governor("ondemand") is False


def test_thp_and_zram(backend, monkeypatch):
    monkeypatch.setattr(linux.common, "read_text", lambda p: "always [madvise]")
    assert "always" in backend.thp_status()
    monkeypatch.setattr(linux.Path, "glob", lambda self, pat: [])
    assert backend.zram_status() == "не используется"


# --------------------------------------------------------------------------- #
#  Корзина
# --------------------------------------------------------------------------- #
def test_trash_items_and_empty(backend, monkeypatch, tmp_path):
    trash = tmp_path / ".local" / "share" / "Trash"
    info = trash / "info"
    files = trash / "files"
    info.mkdir(parents=True)
    files.mkdir()
    (info / "x.trashinfo").write_text("Path=/home/u/x.txt\nDeletionDate=2026-01-01\n")
    (files / "x.txt").write_text("data")
    monkeypatch.setattr(linux.Path, "home",
                        classmethod(lambda cls: tmp_path))
    items = backend.trash_items()
    assert items and items[0]["name"] == "x.txt"
    ok, msg = backend.empty_trash()
    assert ok and "очищена" in msg
