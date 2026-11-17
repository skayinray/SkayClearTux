"""Палитра команд SkayClearTux (Ctrl+K).

Быстрый переход к любому разделу программы по имени. Работает как поиск:
печатаешь часть названия — список сразу фильтруется. Навигация стрелками,
Enter — переход, Esc — закрыть.

Дополнительно умеет запускать несколько «действий» (проверить обновления,
сменить тему, открыть настройки и т. п.).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QVBoxLayout)

from .helptext import help_for


def _score(query: str, text: str) -> int:
    """Простая оценка совпадения: чем раньше и плотнее — тем лучше."""
    q, t = query.lower(), text.lower()
    if not q:
        return 1
    if t.startswith(q):
        return 100
    if q in t:
        return 60 - t.index(q)
    # поиск по подпоследовательности символов
    pos = 0
    hits = 0
    for ch in q:
        idx = t.find(ch, pos)
        if idx == -1:
            return 0
        hits += 1
        pos = idx + 1
    return 20 + hits


class CommandPalette(QDialog):
    """Всплывающее окно быстрого перехода по разделам и действиям."""

    activated = Signal(str)   # ключ страницы
    action = Signal(str)      # имя действия

    def __init__(self, pages: list[tuple[str, str]], parent=None):
        """pages — список (key, title) в порядке следования."""
        super().__init__(parent)
        self.setWindowTitle("Палитра команд")
        self.setModal(True)
        self.setObjectName("Palette")
        self.setMinimumWidth(560)

        self._pages = pages
        self._entries: list[tuple[str, str, str]] = []  # (kind, key, title)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Куда перейти? Начни печатать название раздела…")
        self.edit.setClearButtonEnabled(True)
        lay.addWidget(self.edit)

        self.list = QListWidget()
        self.list.setObjectName("PaletteList")
        self.list.setMinimumHeight(320)
        lay.addWidget(self.list, 1)

        hint = QLabel("Стрелки — выбор · Enter — открыть · Esc — закрыть")
        hint.setObjectName("CardSub")
        lay.addWidget(hint)

        self._build_entries()
        self._refresh("")

        self.edit.textChanged.connect(self._refresh)
        self.edit.returnPressed.connect(self._activate_current)
        self.list.itemActivated.connect(lambda _it: self._activate_current())
        self.list.itemClicked.connect(lambda _it: self._activate_current())

    # ------------------------------------------------------------------ данные
    def _build_entries(self) -> None:
        self._entries = [("page", key, title) for key, title in self._pages]
        self._entries += [
            ("action", "check_updates", "Проверить обновления"),
            ("action", "themes", "Сменить тему оформления"),
            ("action", "settings", "Открыть настройки"),
            ("action", "help", "Открыть справку"),
            ("action", "about", "О программе"),
            ("action", "quit", "Выйти из SkayClearTux"),
        ]

    def _refresh(self, query: str) -> None:
        query = query.strip()
        scored: list[tuple[int, tuple[str, str, str]]] = []
        for entry in self._entries:
            kind, key, title = entry
            _cat, name, _desc = help_for(key) if kind == "page" else ("", title, "")
            text = f"{title} {name}"
            score = _score(query, text)
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda item: item[0], reverse=True)

        self.list.clear()
        for _score_value, (kind, key, title) in scored:
            if kind == "page":
                _cat, name, desc = help_for(key)
                label = f"{name}  ·  {title}" if name and name != title else title
                item = QListWidgetItem(label)
                item.setToolTip(desc)
            else:
                item = QListWidgetItem(f"Действие: {title}")
            item.setData(Qt.UserRole, (kind, key))
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    # --------------------------------------------------------------- активация
    def _activate_current(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        kind, key = item.data(Qt.UserRole)
        self.accept()
        if kind == "page":
            self.activated.emit(key)
        else:
            self.action.emit(key)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.edit.setFocus()
        self.edit.selectAll()
