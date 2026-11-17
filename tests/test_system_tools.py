"""Юнит-тесты фасада ``skaycleartux.system_tools``.

Проверяем, что фасад просто делегирует вызовы бэкенду, сохраняет старые
алиасы и корректно работает с заметками/копированием. Сам бэкенд
подменяется фейком, поэтому тесты не зависят от ОС.
"""
from __future__ import annotations

import subprocess

import pytest

from skaycleartux import system_tools as st


class FakeBackend:
    """Запоминает вызовы и отдаёт заранее заданные значения."""

    def __init__(self):
        self.calls: list[tuple] = []

    def _record(self, name, *args, value=None):
        self.calls.append((name, *args))
        return value

    def list_processes(self):
        return self._record("list_processes", value=[{"pid": 1}])

    def kill_process(self, pid, force=False):
        return self._record("kill_process", pid, force, value=(True, "ok"))

    def list_services(self):
        return self._record("list_services", value=[{"unit": "a"}])

    def service_action(self, unit, action):
        return self._record("service_action", unit, action, value=(True, "ok"))

    def package_manager(self):
        return self._record("package_manager", value="pacman")

    def search_packages(self, query):
        return self._record("search_packages", query,
                            value=[{"name": query}] if query
                            else [{"name": "installed"}])

    def install_packages(self, names):
        return self._record("install_packages", tuple(names), value=(True, "ok"))

    def remove_packages(self, names):
        return self._record("remove_packages", tuple(names), value=(True, "ok"))

    def package_files(self, pkg):
        return self._record("package_files", pkg, value="files")

    def file_owner(self, path):
        return self._record("file_owner", path, value="owner")

    def package_info(self, pkg):
        return self._record("package_info", pkg, value="info")

    def check_updates(self):
        return self._record("check_updates", value=[{"name": "x"}])

    def system_update(self):
        return self._record("system_update", value=(True, "upgraded"))

    def network_info(self):
        return self._record("network_info", value={"hostname": "h"})

    def ping_test(self, host="1.1.1.1", count=4):
        return self._record("ping_test", host, count, value={"ok": True})

    def public_ip(self):
        return self._record("public_ip", value="1.2.3.4")

    def sensors_info(self):
        return self._record("sensors_info", value=([("cpu", 40.0)], []))

    def memory_info(self):
        return self._record("memory_info", value=(8.0, 4.0))

    def load_avg(self):
        return self._record("load_avg", value=(0.1, 0.2, 0.3))

    def cpu_percent(self):
        return self._record("cpu_percent", value=12.5)

    def cpu_model(self):
        return self._record("cpu_model", value="Fake CPU")

    def uptime(self):
        return self._record("uptime", value="1 ч")

    def battery_info(self):
        return self._record("battery_info", value=None)

    def list_startup(self):
        return self._record("list_startup", value=[{"name": "a"}])

    def set_startup_enabled(self, entry, enabled):
        return self._record("set_startup_enabled", entry, enabled, value=True)

    def disk_usage(self, path=None):
        return self._record("disk_usage", path, value=(100, 50, 50))

    def large_files(self, root, min_mb=100, limit=300):
        return self._record("large_files", root, min_mb, limit, value=[])

    def mounts(self):
        return self._record("mounts", value=[{"src": "/dev/sda1"}])

    def disks_overview(self):
        return self._record("disks_overview", value="disks")

    def smart_health(self):
        return self._record("smart_health", value="SMART OK")

    def hardware_sections(self):
        return self._record("hardware_sections", value=[("CPU", "x")])

    def diagnostics(self):
        return self._record("diagnostics", value=[("d", "x")])

    def boot_analysis(self):
        return self._record("boot_analysis", value=[("b", "x")])

    def list_timers_raw(self):
        return self._record("list_timers_raw", value="timers")

    def journal_entries(self, priority="err", lines=200, unit=""):
        return self._record("journal_entries", priority, lines, unit, value="log")

    def list_modules(self):
        return self._record("list_modules", value=[{"name": "nvidia"}])

    def module_action(self, name, action):
        return self._record("module_action", name, action, value=(True, "ok"))

    def firewall_status(self):
        return self._record("firewall_status", value="active")

    def firewall_status_root(self):
        return self._record("firewall_status_root", value="active")

    def listening_ports(self):
        return self._record("listening_ports", value=[{"local": ":22"}])

    def established_connections(self):
        return self._record("established_connections", value=[{"peer": "x"}])

    def get_swappiness(self):
        return self._record("get_swappiness", value=60)

    def set_swappiness(self, value):
        return self._record("set_swappiness", value, value=True)

    def cpu_governor(self):
        return self._record("cpu_governor", value="performance")

    def cpu_governors(self):
        return self._record("cpu_governors", value=["performance"])

    def set_cpu_governor(self, governor):
        return self._record("set_cpu_governor", governor, value=True)

    def thp_status(self):
        return self._record("thp_status", value="madvise")

    def zram_status(self):
        return self._record("zram_status", value="off")

    def trash_items(self):
        return self._record("trash_items", value=[{"name": "x"}])

    def empty_trash(self):
        return self._record("empty_trash", value=(True, "очищена"))


@pytest.fixture
def fake_backend(monkeypatch):
    fb = FakeBackend()
    monkeypatch.setattr(st, "BACKEND", fb)
    return fb


# --------------------------------------------------------------------------- #
#  Делегирование
# --------------------------------------------------------------------------- #
def test_backend_accessor(fake_backend):
    assert st.backend() is fake_backend


def test_processes_and_services(fake_backend):
    assert st.list_processes() == [{"pid": 1}]
    assert st.kill_process(5, force=True) == (True, "ok")
    assert st.list_services() == [{"unit": "a"}]
    assert st.service_action("u", "start") == (True, "ok")
    assert fake_backend.calls[1] == ("kill_process", 5, True)


def test_packages_and_aliases(fake_backend):
    assert st.package_manager() == "pacman"
    assert st.search_packages("vim") == [{"name": "vim"}]
    assert st.install_packages(["vim"]) == (True, "ok")
    assert st.remove_packages(["vim"]) == (True, "ok")
    assert st.package_files("vim") == "files"
    assert st.file_owner("/bin/vim") == "owner"
    assert st.package_info("vim") == "info"
    # старые имена указывают на те же функции
    assert st.pacman_search is st.search_packages
    assert st.pacman_install is st.install_packages
    assert st.pacman_remove is st.remove_packages
    assert st.pacman_installed() == {"installed"}


def test_updates_network_sensors(fake_backend):
    assert st.check_updates() == [{"name": "x"}]
    assert st.system_update() == (True, "upgraded")
    assert st.network_info() == {"hostname": "h"}
    assert st.ping_test("8.8.8.8", 2) == {"ok": True}
    assert st.public_ip() == "1.2.3.4"
    assert st.sensors_info() == ([("cpu", 40.0)], [])
    assert st.memory_info() == (8.0, 4.0)
    assert st.load_avg() == (0.1, 0.2, 0.3)
    assert st.cpu_percent() == 12.5
    assert st.cpu_model() == "Fake CPU"
    assert st.uptime() == "1 ч"
    assert st.battery_info() is None


def test_startup_disk_hardware(fake_backend, tmp_path):
    assert st.list_startup() == [{"name": "a"}]
    assert st.set_startup_enabled({"name": "a"}, False) is True
    assert st.disk_usage("/") == (100, 50, 50)
    assert st.large_files(tmp_path) == []
    assert st.mounts() == [{"src": "/dev/sda1"}]
    assert st.disks_overview() == "disks"
    assert st.smart_health() == "SMART OK"
    assert st.hardware_sections() == [("CPU", "x")]
    assert st.diagnostics() == [("d", "x")]
    assert st.boot_analysis() == [("b", "x")]
    assert st.list_timers_raw() == "timers"
    assert st.journal_entries("warning", 5, "ssh.service") == "log"
    assert st.list_modules() == [{"name": "nvidia"}]
    assert st.module_action("nvidia", "load") == (True, "ok")
    assert st.firewall_status() == "active"
    assert st.firewall_status_root() == "active"


def test_ports_tweaks_trash(fake_backend):
    assert st.listening_ports() == [{"local": ":22"}]
    assert st.established_connections() == [{"peer": "x"}]
    assert st.get_swappiness() == 60
    assert st.set_swappiness(10) is True
    assert st.cpu_governor() == "performance"
    assert st.cpu_governors() == ["performance"]
    assert st.set_cpu_governor("powersave") is True
    assert st.thp_status() == "madvise"
    assert st.zram_status() == "off"
    assert st.trash_items() == [{"name": "x"}]
    assert st.empty_trash() == (True, "очищена")


# --------------------------------------------------------------------------- #
#  Вспомогательные функции
# --------------------------------------------------------------------------- #
def test_platform_name(monkeypatch):
    monkeypatch.setattr(st.common, "os_short_name", lambda: "Linux")
    assert st.platform_name() == "Linux"
    monkeypatch.setattr(st.common, "os_pretty_name", lambda: "Arch Linux")
    assert st.os_pretty_name() == "Arch Linux"


def test_dir_size_str(tmp_path):
    f = tmp_path / "f.bin"
    f.write_bytes(b"x" * 1024)
    assert st.dir_size_str(str(f)) == "1.0 КБ"
    assert st.dir_size_str(str(tmp_path / "missing")) == "—"


def test_notes_roundtrip(monkeypatch, tmp_path):
    notes = tmp_path / "notes.txt"
    monkeypatch.setattr(st, "NOTES_PATH", notes)
    assert st.load_notes() == ""
    assert st.save_notes("привет") is True
    assert st.load_notes() == "привет"


def test_load_notes_error(monkeypatch, tmp_path):
    monkeypatch.setattr(st, "NOTES_PATH", tmp_path / "nope" / "x")
    assert st.load_notes() == ""


def test_run_rsync_uses_rsync(monkeypatch, tmp_path):
    monkeypatch.setattr(st.common.shutil, "which", lambda n: "/usr/bin/rsync")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "progress output", "")

    monkeypatch.setattr(st.common, "run", fake_run)
    ok, out = st.run_rsync(str(tmp_path), str(tmp_path / "dst"), delete=True)
    assert ok is True
    assert out == "progress output"
    assert "--delete" in captured["cmd"]


def test_run_rsync_falls_back_to_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(st.common.shutil, "which", lambda n: None)
    monkeypatch.setattr(st.common, "copy_tree",
                        lambda src, dst, delete=False: (True, "copied"))
    assert st.run_rsync("a", "b") == (True, "copied")
