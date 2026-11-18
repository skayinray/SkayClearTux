"""Настройки SkayClearTux — обёртка над QSettings с разумными значениями по умолчанию."""
from __future__ import annotations

from PySide6.QtCore import QSettings

CREATOR = "t.me/imneedasleep"

DEFAULTS: dict[str, object] = {
    # оформление
    "theme": "Полночь",
    "ui/animations": True,
    "ui/anim_ms": 220,
    "ui/font_scale": 100,
    "ui/start_page": "dash",
    "ui/remember_window": True,
    "ui/confirm_exit": False,
    "ui/collapsed": "",          # разделы сайдбара, свёрнутые (через запятую)
    "ui/show_tips": True,        # подсказки и описания
    "ui/tray": True,             # значок в системном трее
    "ui/tray_notify": True,      # показывать уведомления из трея
    "ui/close_to_tray": False,   # закрывать окно в трей, а не выходить
    "ui/hotkeys": True,          # глобальные горячие клавиши внутри окна
    "ui/tray_hint_shown": False, # одноразовая подсказка про трей
    "ui/macos_hint_shown": False,# одноразовая подсказка про Gatekeeper (macOS)
    # шахматы
    "chess/difficulty": "Средне",
    "chess/side": "Белые",
    "chess/show_coords": True,
    "chess/show_hints": True,
    "chess/highlight_last": True,
    "chess/animate": True,
    "chess/auto_queen": True,
    "chess/show_move_list": True,
    # шахматы: рейтинг Эло
    "chess/elo": 1200,
    "chess/best_elo": 1200,
    "chess/games": 0,
    "chess/wins": 0,
    "chess/losses": 0,
    "chess/draws": 0,
    # очистка
    "cleaner/confirm": True,
    "cleaner/select_safe": True,
    # инструменты
    "tools/refresh_sec": 5,
    "tools/hide_kernel": True,
    "journal/lines": 200,
    # бэкап
    "backup/src": "",
    "backup/dst": "",
    # Discord Rich Presence
    "discord/enabled": True,
    "discord/client_id": "",
    "discord/show_page": True,
    # обновления
    "update/manifest_url": "",  # пусто = официальный манифест из коробки
    "update/auto_check": True,
    "update/last_check": 0,
}


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "on", "да")


class Settings:
    """Тонкая обёртка: get/get_bool/get_int/set/reset."""

    def __init__(self) -> None:
        self._s = QSettings("SkayClearTux", "SkayClearTux")

    def get(self, key: str, default=None):
        if default is None:
            default = DEFAULTS.get(key)
        return self._s.value(key, default)

    def get_bool(self, key: str) -> bool:
        return _as_bool(self.get(key))

    def get_int(self, key: str) -> int:
        try:
            return int(self.get(key))
        except (TypeError, ValueError):
            return int(DEFAULTS.get(key, 0))

    def set(self, key: str, value) -> None:
        self._s.setValue(key, value)

    def save(self) -> None:
        self._s.sync()

    def reset(self) -> None:
        for key, value in DEFAULTS.items():
            self._s.setValue(key, value)
        self._s.sync()
