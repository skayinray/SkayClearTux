"""Выбор системного бэкенда под текущую ОС.

Использование:

    from .backends import get_backend
    backend = get_backend()
    backend.list_processes()
"""
from __future__ import annotations

from . import common
from .base import NOT_AVAILABLE, BaseBackend

__all__ = ["get_backend", "common", "BaseBackend", "NOT_AVAILABLE"]

_instance: BaseBackend | None = None


def get_backend() -> BaseBackend:
    global _instance
    if _instance is not None:
        return _instance
    fam = common.FAMILY
    try:
        if fam == "linux":
            from .linux import LinuxBackend
            _instance = LinuxBackend()
        elif fam == "macos":
            from .macos import MacOSBackend
            _instance = MacOSBackend()
        elif fam == "windows":
            from .windows import WindowsBackend
            _instance = WindowsBackend()
        else:
            _instance = BaseBackend()
    except Exception:  # noqa: BLE001 — не даём приложению не запуститься
        _instance = BaseBackend()
    return _instance
