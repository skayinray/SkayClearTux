"""Тесты помощников интерфейса и пометки недоступных функций.

Виджеты регистрируются в ``qtbot`` — иначе Qt-объекты уничтожаются уже после
завершения ``QApplication`` и процесс падает при выходе (segfault).
"""
from __future__ import annotations

from PySide6.QtWidgets import QPushButton

from skaycleartux import extra_pages
from skaycleartux import system_tools as st
from skaycleartux.backends.base import NOT_AVAILABLE
from skaycleartux.ui_utils import mark_available, mark_unavailable


def test_mark_unavailable_default_reason(qtbot):
    button = QPushButton("действие")
    qtbot.addWidget(button)
    mark_unavailable(button)
    assert not button.isEnabled()
    assert button.toolTip() == NOT_AVAILABLE


def test_mark_unavailable_custom_reason(qtbot):
    button = QPushButton("действие")
    qtbot.addWidget(button)
    mark_unavailable(button, "только на Linux")
    assert button.toolTip() == "только на Linux"


def test_mark_available_resets(qtbot):
    button = QPushButton("действие")
    qtbot.addWidget(button)
    mark_unavailable(button, "причина")
    mark_available(button)
    assert button.isEnabled()
    assert button.toolTip() == ""


# --------------------------------------------------------------------------- #
#  Пометка в реальных страницах
# --------------------------------------------------------------------------- #
def test_modules_page_marks_actions_unavailable(qtbot, monkeypatch):
    monkeypatch.setattr(st, "list_modules", lambda: [])
    page = extra_pages.ModulesPage(None)
    qtbot.addWidget(page)
    page.refresh()
    assert not page.btn_load.isEnabled()
    assert not page.btn_unload.isEnabled()
    assert not page.name_input.isEnabled()
    assert page.btn_load.toolTip()


def test_modules_page_keeps_actions_when_available(qtbot, monkeypatch):
    monkeypatch.setattr(st, "list_modules", lambda: [
        {"name": "nvidia", "size": "1 МБ", "used": "1", "by": "X"}])
    page = extra_pages.ModulesPage(None)
    qtbot.addWidget(page)
    page.refresh()
    assert page.btn_load.isEnabled()
    assert page.btn_load.toolTip() == ""


def test_tweaks_page_marks_governor_unavailable(qtbot, monkeypatch):
    monkeypatch.setattr(st, "get_swappiness", lambda: 60)
    monkeypatch.setattr(st, "cpu_governors", lambda: [])
    monkeypatch.setattr(st, "cpu_governor", lambda: "—")
    monkeypatch.setattr(st, "thp_status", lambda: "—")
    monkeypatch.setattr(st, "zram_status", lambda: "—")
    page = extra_pages.TweaksPage(None)
    qtbot.addWidget(page)
    page.refresh()
    assert not page.btn_gov.isEnabled()
    assert page.btn_gov.toolTip()


def test_tweaks_page_keeps_governor_when_available(qtbot, monkeypatch):
    monkeypatch.setattr(st, "get_swappiness", lambda: 60)
    monkeypatch.setattr(st, "cpu_governors", lambda: ["powersave", "performance"])
    monkeypatch.setattr(st, "cpu_governor", lambda: "powersave")
    monkeypatch.setattr(st, "thp_status", lambda: "—")
    monkeypatch.setattr(st, "zram_status", lambda: "—")
    page = extra_pages.TweaksPage(None)
    qtbot.addWidget(page)
    page.refresh()
    assert page.btn_gov.isEnabled()
    assert page.btn_gov.toolTip() == ""
