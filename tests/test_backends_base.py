"""Юнит-тесты базового бэкенда ``skaycleartux.backends.base``.

Проверяем, что все непереопределённые методы возвращают безопасную заглушку,
а реализованные в базе (ping, public_ip, диск, крупные файлы) корректно
разбирают вывод и не падают при ошибках.
"""
from __future__ import annotations

import subprocess

from skaycleartux.backends import common
from skaycleartux.backends.base import NOT_AVAILABLE, BaseBackend


def test_not_available_stubs():
    b = BaseBackend()
    assert b.name == "base"
    assert b.list_processes() == []
    assert b.kill_process(1) == (False, NOT_AVAILABLE)
    assert b.list_services() == []
    assert b.service_action("x", "start") == (False, NOT_AVAILABLE)
    assert b.package_manager() == ""
    assert b.search_packages("q") == []
    assert b.install_packages(["a"]) == (False, NOT_AVAILABLE)
    assert b.remove_packages(["a"]) == (False, NOT_AVAILABLE)
    assert b.package_files("a") == NOT_AVAILABLE
    assert b.file_owner("/x") == NOT_AVAILABLE
    assert b.package_info("a") == NOT_AVAILABLE
    assert b.check_updates() == []
    assert b.system_update() == (False, NOT_AVAILABLE)
    assert b.sensors_info() == ([], [])
    assert b.memory_info() == (0.0, 0.0)
    assert b.cpu_percent() == 0.0
    assert b.uptime() == "—"
    assert b.battery_info() is None
    assert b.list_startup() == []
    assert b.set_startup_enabled({}, True) is False
    assert b.root_path() == "/"
    assert b.mounts() == []
    assert b.disks_overview() == NOT_AVAILABLE
    assert b.smart_health() == NOT_AVAILABLE
    assert b.hardware_sections() == []
    assert b.diagnostics() == []
    assert b.boot_analysis() == [("Анализ загрузки", NOT_AVAILABLE)]
    assert b.list_timers_raw() == NOT_AVAILABLE
    assert b.list_modules() == []
    assert b.module_action("x", "load") == (False, NOT_AVAILABLE)
    assert b.firewall_status() == NOT_AVAILABLE
    assert b.firewall_status_root() == NOT_AVAILABLE
    assert b.journal_entries() == NOT_AVAILABLE
    assert b.listening_ports() == []
    assert b.established_connections() == []
    assert b.get_swappiness() == 60
    assert b.set_swappiness(10) is False
    assert b.cpu_governor() == "—"
    assert b.cpu_governors() == []
    assert b.set_cpu_governor("x") is False
    assert b.thp_status() == "—"
    assert b.zram_status() == "—"
    assert b.trash_items() == []
    assert b.empty_trash() == (False, NOT_AVAILABLE)


def test_network_info_default():
    info = BaseBackend().network_info()
    assert set(info) == {"hostname", "interfaces", "route", "dns"}
    assert info["interfaces"] == []


def test_ping_test_parses(monkeypatch):
    out = ("3 packets transmitted, 3 received, 0% packet loss\n"
           "rtt min/avg/max = 1.0/2.5/4.0 ms\n")
    monkeypatch.setattr(common, "FAMILY", "linux")
    monkeypatch.setattr(common, "run",
                        lambda *a, **k: subprocess.CompletedProcess([], 0, out, ""))
    res = BaseBackend().ping_test("1.1.1.1", 3)
    assert res["ok"] is True
    assert "loss" in res["loss"]
    assert "avg" in res["avg"]


def test_ping_test_failure(monkeypatch):
    monkeypatch.setattr(common, "FAMILY", "linux")
    monkeypatch.setattr(common, "run",
                        lambda *a, **k: subprocess.CompletedProcess([], 1, "", ""))
    assert BaseBackend().ping_test()["ok"] is False


def test_public_ip_ok(monkeypatch):
    monkeypatch.setattr(common, "run",
                        lambda *a, **k: subprocess.CompletedProcess([], 0, "9.9.9.9\n", ""))
    assert BaseBackend().public_ip() == "9.9.9.9"


def test_public_ip_invalid_then_empty(monkeypatch):
    monkeypatch.setattr(common, "run",
                        lambda *a, **k: subprocess.CompletedProcess([], 0, "not an ip address here", ""))
    assert BaseBackend().public_ip() == ""


def test_disk_usage(monkeypatch, tmp_path):
    b = BaseBackend()
    monkeypatch.setattr(b, "root_path", lambda: str(tmp_path))
    total, free, percent = b.disk_usage()
    assert total > 0
    assert 0 <= percent <= 100


def test_disk_usage_bad_path():
    assert BaseBackend().disk_usage("/definitely/not/here") == (0, 0, 0)


def test_load_avg_fallback(monkeypatch):
    monkeypatch.setattr(common.os, "getloadavg", None, raising=False)
    assert BaseBackend().load_avg() == (0.0, 0.0, 0.0)


def test_large_files(tmp_path):
    (tmp_path / "small.txt").write_bytes(b"x" * 10)
    (tmp_path / "big.bin").write_bytes(b"x" * (2 * 1024 * 1024))
    (tmp_path / "skipdir").mkdir()
    (tmp_path / "skipdir" / "node_modules").mkdir()
    (tmp_path / "skipdir" / "node_modules" / "huge.bin").write_bytes(b"x" * (3 * 1024 * 1024))
    found = BaseBackend().large_files(str(tmp_path), min_mb=1, limit=10)
    names = [p for p, _ in found]
    assert any(n.endswith("big.bin") for n in names)
    assert not any("node_modules" in n for n in names)
