"""Мелкие помощники интерфейса.

Здесь собраны функции, общие для нескольких экранов. Пока это пометка
недоступных на текущей ОС функций: виджет отключается и получает подсказку,
чтобы пользователь понимал, почему кнопка неактивна.
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from .backends.base import NOT_AVAILABLE


def mark_unavailable(widget: QWidget, reason: str = NOT_AVAILABLE) -> None:
    """Отключает виджет и показывает причину в подсказке."""
    widget.setEnabled(False)
    widget.setToolTip(reason)


def mark_available(widget: QWidget) -> None:
    """Возвращает виджет в активное состояние и убирает подсказку."""
    widget.setEnabled(True)
    widget.setToolTip("")
