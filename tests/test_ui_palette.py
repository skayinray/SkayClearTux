"""UI-тесты палитры команд (Ctrl+K) — ``skaycleartux.palette``.

Проверяем поиск/фильтрацию, поведение при пустом вводе, выбор элемента и
закрытие по Esc. Работает в offscreen-режиме (см. tests/conftest.py).
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog

from skaycleartux.palette import CommandPalette, _score

PAGES = [("dash", "Главная"), ("cleaner", "Очистка"),
         ("themes", "Темы"), ("settings", "Настройки")]


@pytest.fixture
def palette(qtbot):
    dlg = CommandPalette(PAGES)
    qtbot.addWidget(dlg)
    return dlg


# --------------------------------------------------------------------------- #
#  Оценка совпадения
# --------------------------------------------------------------------------- #
def test_score_empty_query():
    assert _score("", "что угодно") == 1


def test_score_prefix_beats_substring():
    assert _score("оч", "очистка") == 100
    assert 0 < _score("чист", "очистка") < 100


def test_score_subsequence():
    assert _score("глв", "главная") == 20 + 3


def test_score_no_match():
    assert _score("zzz", "очистка") == 0


# --------------------------------------------------------------------------- #
#  Наполнение и фильтрация
# --------------------------------------------------------------------------- #
def test_entries_include_pages_and_actions(palette):
    kinds = {kind for kind, _key, _title in palette._entries}
    assert kinds == {"page", "action"}
    keys = [key for kind, key, _t in palette._entries if kind == "page"]
    assert keys == [k for k, _ in PAGES]


def test_empty_query_shows_everything(palette):
    palette._refresh("")
    assert palette.list.count() == len(palette._entries)
    # первый элемент выбран автоматически
    assert palette.list.currentRow() == 0


def test_query_filters(palette):
    palette._refresh("очис")
    titles = [palette.list.item(i).text() for i in range(palette.list.count())]
    assert any("Очистка" in t for t in titles)
    assert len(titles) < len(palette._entries)


def test_query_matches_action(palette):
    palette._refresh("тему")
    labels = [palette.list.item(i).text() for i in range(palette.list.count())]
    assert any("тему" in t.lower() for t in labels)


def test_no_match_clears_list(palette):
    palette._refresh("ъъъъ-нет-такого")
    assert palette.list.count() == 0
    assert palette.list.currentItem() is None


# --------------------------------------------------------------------------- #
#  Активация
# --------------------------------------------------------------------------- #
def test_activation_emits_page_signal(palette):
    seen = []
    palette.activated.connect(seen.append)
    palette._refresh("очис")
    palette._activate_current()
    assert seen == ["cleaner"]
    assert palette.result() == QDialog.DialogCode.Accepted


def test_activation_emits_action_signal(palette):
    seen = []
    palette.action.connect(seen.append)
    palette._refresh("сменить тему")
    palette._activate_current()
    assert seen == ["themes"]


def test_activation_without_selection_does_nothing(palette):
    seen = []
    palette.activated.connect(seen.append)
    palette.action.connect(seen.append)
    palette._refresh("ъъъъ-нет-такого")
    palette._activate_current()
    assert seen == []


def test_escape_rejects(palette, qtbot):
    called = {}
    palette.reject = lambda: called.setdefault("reject", True)
    event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    palette.keyPressEvent(event)
    assert called.get("reject") is True


def test_other_key_delegates_to_super(palette):
    # обычная клавиша не должна падать и не должна закрывать окно
    event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_A, Qt.NoModifier, "a")
    palette.keyPressEvent(event)  # не бросает
