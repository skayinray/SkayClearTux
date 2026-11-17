"""UI-тесты главного окна — ``skaycleartux.main_window``.

Проверяют состав разделов, навигацию, горячие клавиши (в т.ч. Ctrl+K),
переключение тем, сворачивание секций и обновления. Реальная сеть и трей
не используются (offscreen).

Главное окно тяжёлое, а ``QApplication.setStyleSheet`` перерисовывает все
живые окна, поэтому создаём его один раз на модуль и сбрасываем состояние
перед каждым тестом.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent

from skaycleartux import themes
from skaycleartux.main_window import NAV


@pytest.fixture(scope="module")
def main_window(qapp, ui_settings_dir):
    from skaycleartux.main_window import MainWindow

    win = MainWindow()
    win.resize(1200, 780)
    yield win
    win._quitting = True
    win.close()


@pytest.fixture(autouse=True)
def _fresh_state(main_window):
    """Сбрасывает настройки и состояние окна перед каждым тестом."""
    s = main_window.settings
    s.reset()
    main_window._update_available = None
    main_window._update_busy = False
    main_window.banner.setVisible(False)
    main_window.presence = None
    main_window.apply_theme(themes.DEFAULT_THEME)
    main_window._apply_collapsed()
    main_window._setup_shortcuts()
    main_window._goto("dash")
    yield


# --------------------------------------------------------------------------- #
#  Состав страниц и навигация
# --------------------------------------------------------------------------- #
def test_page_count_matches_nav(main_window):
    expected = sum(len(items) for _section, items in NAV)
    assert main_window.stack.count() == expected


def test_key_index_is_sequential(main_window):
    expected = [key for _s, items in NAV for _label, key in items]
    assert list(main_window.key_index) == expected
    assert list(main_window.key_index.values()) == list(range(len(expected)))


def test_index_key_is_inverse(main_window):
    for key, index in main_window.key_index.items():
        assert main_window.index_key[index] == key


def test_goto_changes_page_and_checks_button(main_window):
    main_window._goto("cleaner")
    assert main_window.stack.currentIndex() == main_window.key_index["cleaner"]
    assert main_window.nav_buttons[main_window.key_index["cleaner"]].isChecked()


def test_goto_unknown_falls_back_to_first(main_window):
    main_window._goto("нет-такого")
    assert main_window.stack.currentIndex() == 0


def test_page_list_order(main_window):
    assert main_window._page_list() == [
        (key, label) for _s, items in NAV for label, key in items]


def test_cycle_page_wraps(main_window):
    count = main_window.stack.count()
    main_window._goto(main_window.index_key[0])
    main_window._cycle_page(-1)
    assert main_window.stack.currentIndex() == count - 1
    main_window._cycle_page(1)
    assert main_window.stack.currentIndex() == 0


# --------------------------------------------------------------------------- #
#  Горячие клавиши и палитра
# --------------------------------------------------------------------------- #
def _shortcut_strings(win) -> set[str]:
    return {sc.key().toString() for sc in win._shortcuts}


def test_shortcuts_registered(main_window):
    seqs = _shortcut_strings(main_window)
    assert "Ctrl+K" in seqs
    assert "Ctrl+F" in seqs
    assert "Ctrl+Q" in seqs
    assert "Ctrl+H" in seqs
    assert "F1" in seqs


def test_hotkeys_disabled(main_window):
    main_window.settings.set("ui/hotkeys", False)
    main_window._setup_shortcuts()
    assert main_window._shortcuts == []


def test_ctrl_k_opens_palette(main_window, qtbot, qapp, monkeypatch):
    calls = []
    monkeypatch.setattr(main_window, "open_palette", lambda: calls.append(1))
    main_window._setup_shortcuts()  # пересоздаём шорткаты с подменённым методом
    main_window.show()
    main_window.activateWindow()
    qapp.processEvents()
    qtbot.keyClick(main_window, Qt.Key_K, Qt.ControlModifier)
    assert calls, "Ctrl+K не открыл палитру"


def test_run_action_navigation(main_window, monkeypatch):
    main_window._run_action("themes")
    assert main_window.stack.currentIndex() == main_window.key_index["themes"]
    main_window._run_action("settings")
    assert main_window.stack.currentIndex() == main_window.key_index["settings"]
    main_window._run_action("help")
    assert main_window.stack.currentIndex() == main_window.key_index["help"]


def test_run_action_check_updates(main_window, monkeypatch):
    calls = []
    monkeypatch.setattr(main_window, "check_updates",
                        lambda silent=False: calls.append(silent))
    main_window._run_action("check_updates")
    assert calls == [False]


def test_run_action_quit(main_window, monkeypatch):
    called = []
    monkeypatch.setattr(main_window, "_quit", lambda: called.append(1))
    main_window._run_action("quit")
    assert called == [1]


# --------------------------------------------------------------------------- #
#  Темы
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", list(themes.THEMES))
def test_apply_each_theme(main_window, name):
    main_window.apply_theme(name)
    assert main_window.theme_name == name
    assert main_window.colors == themes.THEMES[name]
    assert main_window.theme_hint.text() == f"Тема: {name}"


def test_apply_unknown_theme_ignored(main_window):
    before = main_window.theme_name
    main_window.apply_theme("нет такой темы")
    assert main_window.theme_name == before


def test_rapid_theme_switching(main_window):
    for _ in range(4):
        for name in themes.THEMES:
            main_window.apply_theme(name)
    assert main_window.theme_name in themes.THEMES


# --------------------------------------------------------------------------- #
#  Секции, обновление страницы, настройки
# --------------------------------------------------------------------------- #
def test_toggle_section_collapses(main_window):
    header = main_window.section_headers["Обзор"]
    main_window._toggle_section("Обзор")
    assert "Обзор" in main_window._collapsed_set()
    assert header.text().startswith("+")
    main_window._toggle_section("Обзор")
    assert "Обзор" not in main_window._collapsed_set()
    assert header.text().startswith("−")


def test_refresh_current_calls_page_refresh(main_window):
    called = []
    page = main_window.stack.currentWidget()
    page.refresh = lambda: called.append(1)
    main_window._refresh_current()
    assert called == [1]


def test_refresh_current_without_method(main_window):
    page = main_window.stack.currentWidget()
    for name in ("refresh", "reload", "scan", "_refresh", "reload_data"):
        if hasattr(page, name):
            delattr(page, name)
    main_window._refresh_current()  # не должно падать


def test_on_settings_changed_does_not_crash(main_window):
    main_window._on_settings_changed()


def test_on_page_changed_without_presence(main_window):
    main_window.presence = None
    main_window._on_page_changed(0)  # просто ничего не делает


# --------------------------------------------------------------------------- #
#  Обновления
# --------------------------------------------------------------------------- #
def test_updates_checked_shows_banner(main_window, monkeypatch):
    monkeypatch.setattr("skaycleartux.updater.is_newer", lambda *a, **k: True)
    main_window._updates_checked(
        {"ok": True, "data": {"version": "9.9.9", "notes": "новое"}}, silent=True)
    assert main_window._update_available is not None
    assert "9.9.9" in main_window.banner_label.text()


def test_updates_checked_error_silent(main_window):
    main_window._updates_checked({"ok": False, "error": "нет сети"}, silent=True)
    assert main_window._update_available is None


def test_check_updates_without_url_is_silent(main_window):
    main_window.settings.set("update/manifest_url", "")
    # silent=True не показывает диалог и просто выходит
    main_window.check_updates(silent=True)


def test_do_update_without_info(main_window):
    main_window._update_available = None
    main_window._do_update()  # без данных — просто выход


# --------------------------------------------------------------------------- #
#  Подсказка про Gatekeeper (только macOS)
# --------------------------------------------------------------------------- #
def test_macos_hint_only_on_macos(main_window, monkeypatch):
    from skaycleartux import main_window as mw

    shown: list = []

    class _FakeTimer:
        @staticmethod
        def singleShot(ms, fn):
            fn()

    class _FakeBox:
        @staticmethod
        def information(*args, **kwargs):
            shown.append(args)

    monkeypatch.setattr(mw, "QTimer", _FakeTimer)
    monkeypatch.setattr(mw, "QMessageBox", _FakeBox)
    main_window.settings.set("ui/macos_hint_shown", False)

    monkeypatch.setattr(mw.platform_common, "FAMILY", "linux")
    main_window._maybe_macos_hint()
    assert shown == []
    assert main_window.settings.get_bool("ui/macos_hint_shown") is False

    monkeypatch.setattr(mw.platform_common, "FAMILY", "macos")
    main_window._maybe_macos_hint()
    assert len(shown) == 1
    assert main_window.settings.get_bool("ui/macos_hint_shown") is True

    # повторный запуск подсказку не показывает
    main_window._maybe_macos_hint()
    assert len(shown) == 1


# --------------------------------------------------------------------------- #
#  Трей и закрытие
# --------------------------------------------------------------------------- #
def test_no_tray_in_offscreen(main_window):
    from PySide6.QtWidgets import QSystemTrayIcon
    if not QSystemTrayIcon.isSystemTrayAvailable():
        assert main_window._tray is None


def test_close_event_when_quitting(main_window):
    main_window._quitting = True
    event = QCloseEvent()
    main_window.closeEvent(event)
    assert event.isAccepted()
