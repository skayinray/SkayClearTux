"""Тесты выбора бэкенда (``skaycleartux.backends.get_backend``)."""
from __future__ import annotations

import pytest

from skaycleartux import backends
from skaycleartux.backends import common
from skaycleartux.backends.base import BaseBackend


@pytest.fixture(autouse=True)
def _reset_instance(monkeypatch):
    monkeypatch.setattr(backends, "_instance", None)
    yield
    monkeypatch.setattr(backends, "_instance", None)


@pytest.mark.parametrize("family,expected_name", [
    ("linux", "linux"),
    ("macos", "macos"),
    ("windows", "windows"),
    ("other", "base"),
])
def test_get_backend_by_family(monkeypatch, family, expected_name):
    monkeypatch.setattr(common, "FAMILY", family)
    assert backends.get_backend().name == expected_name


def test_get_backend_caches(monkeypatch):
    monkeypatch.setattr(common, "FAMILY", "linux")
    first = backends.get_backend()
    second = backends.get_backend()
    assert first is second


def test_get_backend_falls_back_on_error(monkeypatch):
    monkeypatch.setattr(common, "FAMILY", "linux")

    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("не удалось")

    monkeypatch.setattr(backends, "_instance", None)
    import skaycleartux.backends.linux as linux_mod
    monkeypatch.setattr(linux_mod, "LinuxBackend", Boom)
    assert isinstance(backends.get_backend(), BaseBackend)


def test_not_available_exported():
    assert backends.NOT_AVAILABLE
    assert backends.common is common
