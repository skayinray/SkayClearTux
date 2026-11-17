"""Общая настройка тестов SkayClearTux.

- кладёт корень репозитория в ``sys.path`` (запуск без установки пакета);
- включает offscreen-режим Qt, чтобы UI-тесты шли без дисплея и в CI;
- выбирает PySide6 для pytest-qt;
- даёт общие фикстуры для подмены запуска подпроцессов.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

# --- Qt в offscreen и явный биндинг (до первого импорта PySide6) -------------
import os
import sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTEST_QT_API", "pyside6")
# стабильность в CI/без GPU
os.environ.setdefault("QT_OPENGL", "software")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def make_result(cmd=None, returncode: int = 0, stdout: str = "",
                stderr: str = "") -> subprocess.CompletedProcess:
    """Быстрый конструктор CompletedProcess для тестов."""
    return subprocess.CompletedProcess(cmd or [], returncode, stdout, stderr)


class FakeRunner:
    """Подменяет ``common.run``: отдаёт заранее заданные ответы.

    Ответ можно задать функцией ``handler(cmd) -> CompletedProcess`` либо
    словарём ``{первое_слово_команды: CompletedProcess}``.
    """

    def __init__(self, handler=None, responses=None, default=None):
        self.handler = handler
        self.responses = responses or {}
        self.default = default if default is not None else make_result()
        self.calls: list[list[str]] = []
        self.kwargs: list[dict] = []

    def __call__(self, cmd, **kwargs):
        cmd = [str(c) for c in cmd]
        self.calls.append(cmd)
        self.kwargs.append(kwargs)
        if self.handler is not None:
            return self.handler(cmd, **kwargs)
        key = cmd[0] if cmd else ""
        if key in self.responses:
            value = self.responses[key]
            return value(cmd) if callable(value) else value
        return self.default

    # удобные проверки
    def commands(self) -> list[list[str]]:
        return self.calls

    def first(self) -> list[str]:
        return self.calls[0] if self.calls else []


@pytest.fixture
def fake_run(monkeypatch):
    """Патчит ``common.run`` и возвращает FakeRunner.

    Возвращает фабрику: ``fake_run(handler=..., responses=...)`` — так тест
    сам решает, какие ответы нужны. Патчится модуль ``common``, поэтому
    подмена видна всем бэкендам, которые обращаются к ``common.run``.
    """
    from skaycleartux.backends import common

    created: list[FakeRunner] = []

    def factory(handler=None, responses=None, default=None) -> FakeRunner:
        runner = FakeRunner(handler=handler, responses=responses, default=default)
        monkeypatch.setattr(common, "run", runner)
        created.append(runner)
        return runner

    return factory


# --------------------------------------------------------------------------- #
#  UI-тесты (pytest-qt)
# --------------------------------------------------------------------------- #
@pytest.fixture
def isolated_settings(tmp_path):
    """Изолирует QSettings в временный каталог, чтобы тесты не трогали
    настоящие настройки пользователя и не влияли друг на друга."""
    from PySide6.QtCore import QSettings

    for fmt in (QSettings.IniFormat, QSettings.NativeFormat):
        QSettings.setPath(fmt, QSettings.UserScope, str(tmp_path / "conf"))
        QSettings.setPath(fmt, QSettings.SystemScope, str(tmp_path / "conf"))
    QSettings("SkayClearTux", "SkayClearTux").clear()
    yield tmp_path
    QSettings("SkayClearTux", "SkayClearTux").clear()


@pytest.fixture(scope="module")
def ui_settings_dir(tmp_path_factory):
    """Каталог для QSettings на весь модуль UI-тестов.

    Главное окно тяжёлое, поэтому создаётся один раз на модуль (см.
    ``tests/test_ui_main_window.py``); настройки при этом изолируются.
    """
    from PySide6.QtCore import QSettings

    path = tmp_path_factory.mktemp("qsettings")
    for fmt in (QSettings.IniFormat, QSettings.NativeFormat):
        QSettings.setPath(fmt, QSettings.UserScope, str(path))
        QSettings.setPath(fmt, QSettings.SystemScope, str(path))
    QSettings("SkayClearTux", "SkayClearTux").clear()
    return path
def pytest_collection_modifyitems(config, items):
    if os.environ.get('GITHUB_ACTIONS') == 'true' and sys.platform in ('win32', 'darwin'):
        items[:] = [item for item in items if 'test_ui' not in item.nodeid and 'test_main_window' not in item.nodeid]
