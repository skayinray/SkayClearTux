"""Дополнительные экраны SkayClearTux: монитор, большие файлы, обновления, порты,
железо, диагностика, твики, заметки, генератор паролей."""
from __future__ import annotations

import collections
import secrets
import string
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox,
                               QFileDialog, QFrame, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QScrollArea, QSpinBox, QTabWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from . import system_tools as st
from .cleaner import human
from .helptext import help_for
from .pages import SystemInfo, Worker
from .ui_utils import mark_available, mark_unavailable

MONO = QFont("DejaVu Sans Mono")


def card() -> QFrame:
    f = QFrame()
    f.setObjectName("Card")
    return f


def dim(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Dim")
    lbl.setWordWrap(True)
    return lbl


def title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("H1")
    return lbl


class PageHeader(QWidget):
    """Заголовок страницы с коротким описанием и кнопкой «?» (подробности)."""

    def __init__(self, title_text: str, help_text: str = "", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.title_label = QLabel(title_text)
        self.title_label.setObjectName("H1")
        row.addWidget(self.title_label)
        if help_text:
            btn = QPushButton("?")
            btn.setObjectName("Help")
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.WhatsThisCursor)
            btn.setToolTip("Что делает этот раздел")
            btn.clicked.connect(
                lambda: QMessageBox.information(self, title_text, help_text))
            row.addWidget(btn)
        row.addStretch(1)
        lay.addLayout(row)
        if help_text:
            sub = QLabel(help_text)
            sub.setObjectName("Dim")
            sub.setWordWrap(True)
            lay.addWidget(sub)



def table(columns: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(columns))
    t.setHorizontalHeaderLabels(columns)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    t.horizontalHeader().setStretchLastSection(True)
    return t


def _cell(text: str, align_right: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    if align_right:
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return item


def _mono(text: str) -> QPlainTextEdit:
    edit = QPlainTextEdit(text)
    edit.setReadOnly(True)
    edit.setFont(MONO)
    edit.setLineWrapMode(QPlainTextEdit.NoWrap)
    return edit


# =========================================================================== #
class Spark(QWidget):
    """Живой график с градиентной заливкой."""

    def __init__(self, title_text: str, accent: str, maximum: float = 100.0):
        super().__init__()
        self.title_text = title_text
        self.accent = accent
        self.maximum = maximum
        self.values: collections.deque[float] = collections.deque(maxlen=90)
        self.setMinimumHeight(150)

    def push(self, value: float) -> None:
        self.values.append(value)
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        pad = 14
        plot_h = h - pad * 2
        # сетка
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        for i in range(1, 4):
            y = pad + plot_h * i / 4
            p.drawLine(pad, int(y), w - pad, int(y))
        # заголовок и текущее значение
        p.setPen(QColor(self.accent))
        f = QFont("DejaVu Sans")
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        cur = self.values[-1] if self.values else 0
        p.drawText(pad, pad + 2, f"{self.title_text}   {cur:.0f}%")
        # график
        if len(self.values) >= 2:
            n = len(self.values)
            step = (w - pad * 2) / (self.values.maxlen - 1)
            pts = []
            for i, v in enumerate(self.values):
                x = w - pad - (n - 1 - i) * step
                y = pad + plot_h * (1 - min(v, self.maximum) / self.maximum)
                pts.append((x, y))
            # заливка
            grad = QLinearGradient(0, pad, 0, pad + plot_h)
            grad.setColorAt(0.0, QColor(self.accent).lighter(120))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            from PySide6.QtGui import QPainterPath
            path = QPainterPath()
            path.moveTo(pts[0][0], pad + plot_h)
            for x, y in pts:
                path.lineTo(x, y)
            path.lineTo(pts[-1][0], pad + plot_h)
            path.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(grad)
            p.setOpacity(0.35)
            p.drawPath(path)
            p.setOpacity(1.0)
            # линия
            p.setPen(QPen(QColor(self.accent), 2))
            p.setBrush(Qt.NoBrush)
            line = QPainterPath()
            line.moveTo(*pts[0])
            for pt in pts[1:]:
                line.lineTo(*pt)
            p.drawPath(line)
        p.end()


class MonitorPage(QWidget):
    def __init__(self, settings, theme_colors: dict, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.colors = theme_colors
        self.info = SystemInfo()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        root.addWidget(title("Монитор"))
        root.addWidget(dim("Графики нагрузки процессора и памяти в реальном времени"))

        self.cpu = Spark("ЦП", self.colors["accent"])
        self.ram = Spark("Память", self.colors["success"])
        for spark in (self.cpu, self.ram):
            c = card()
            lay = QVBoxLayout(c)
            lay.setContentsMargins(10, 10, 10, 10)
            lay.addWidget(spark)
            root.addWidget(c, 1)

        self.details = QLabel("—")
        self.details.setObjectName("CardSub")
        root.addWidget(self.details)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    def apply_theme(self, colors: dict) -> None:
        self.colors = colors
        self.cpu.accent = colors["accent"]
        self.ram.accent = colors["success"]
        self.cpu.update()
        self.ram.update()

    def _tick(self) -> None:
        if not (self.isVisible() and self.window().isActiveWindow()):
            return
        cpu = self.info.cpu_percent()
        total, used = self.info.mem()
        self.cpu.push(cpu)
        self.ram.push(100.0 * used / total if total else 0.0)
        self.details.setText(
            f"ЦП: {cpu:.0f}%   ·   Память: {used:.1f} / {total:.1f} ГБ   ·   "
            f"Uptime: {self.info.uptime()}")


# =========================================================================== #
class LargeFilesPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._worker = None
        self._rows: list[tuple[str, int]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(title("Большие файлы"))
        root.addWidget(dim("Поиск самых крупных файлов в домашнем каталоге"))

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Минимум, МБ"))
        self.min_mb = QSpinBox()
        self.min_mb.setRange(1, 10000)
        self.min_mb.setValue(100)
        bar.addWidget(self.min_mb)
        self.btn_scan = QPushButton("Искать")
        self.btn_scan.setObjectName("Accent")
        self.btn_scan.clicked.connect(self.scan)
        bar.addWidget(self.btn_scan)
        bar.addStretch(1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        bar.addWidget(self.status)
        root.addLayout(bar)

        self.table = table(["Файл", "Размер"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(False)
        root.addWidget(self.table, 1)

        act = QHBoxLayout()
        self.btn_open = QPushButton("Открыть папку")
        self.btn_open.clicked.connect(self._open_folder)
        self.btn_copy = QPushButton("Копировать путь")
        self.btn_copy.clicked.connect(self._copy_path)
        self.btn_trash = QPushButton("В корзину")
        self.btn_trash.setObjectName("Danger")
        self.btn_trash.clicked.connect(self._trash)
        act.addWidget(self.btn_open)
        act.addWidget(self.btn_copy)
        act.addWidget(self.btn_trash)
        act.addStretch(1)
        root.addLayout(act)

    def scan(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        self.btn_scan.setEnabled(False)
        self.status.setText("Сканирую домашний каталог…")
        root = Path.home()
        min_mb = self.min_mb.value()
        self._worker = Worker(lambda: st.large_files(root, min_mb))
        self._worker.done.connect(self._done)
        self._worker.start()

    def _done(self, rows) -> None:
        self.btn_scan.setEnabled(True)
        self._rows = rows or []
        self.table.setRowCount(len(self._rows))
        for r, (path, size) in enumerate(self._rows):
            self.table.setItem(r, 0, _cell(path))
            self.table.setItem(r, 1, _cell(human(size), True))
        self.status.setText(f"Найдено: {len(self._rows)}")

    def _selected_path(self) -> str | None:
        row = self.table.currentRow()
        return self._rows[row][0] if 0 <= row < len(self._rows) else None

    def _open_folder(self) -> None:
        path = self._selected_path()
        if path:
            subprocess.Popen(["xdg-open", str(Path(path).parent)])

    def _copy_path(self) -> None:
        path = self._selected_path()
        if path:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(path)
            self.status.setText("Путь скопирован")

    def _trash(self) -> None:
        path = self._selected_path()
        if not path:
            return
        tool = "gio" if shutil_which("gio") else ("trash-put" if shutil_which("trash-put") else None)
        if tool == "gio":
            subprocess.run(["gio", "trash", path])
        elif tool:
            subprocess.run([tool, path])
        else:
            self.status.setText("Нет gio/trash-put — удали вручную")
            return
        self.status.setText("Перемещено в корзину")
        self.scan()


def shutil_which(name: str) -> str | None:
    import shutil
    return shutil.which(name)


# =========================================================================== #
class UpdatesPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._busy = False
        self._rows: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(title("Обновления"))
        root.addWidget(dim("Проверка и установка обновлений системы "
                           "(pacman/apt/dnf/zypper/apk — Linux, Homebrew — macOS, "
                           "winget — Windows)"))

        bar = QHBoxLayout()
        self.btn_check = QPushButton("Проверить обновления")
        self.btn_check.clicked.connect(self.check)
        self.btn_update = QPushButton("Обновить систему")
        self.btn_update.setObjectName("Accent")
        self.btn_update.clicked.connect(self.update)
        bar.addWidget(self.btn_check)
        bar.addWidget(self.btn_update)
        bar.addStretch(1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        bar.addWidget(self.status)
        root.addLayout(bar)

        self.table = table(["Пакет", "Текущая", "Новая"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        root.addWidget(self.table, 2)

        self.log = _mono("")
        self.log.setPlaceholderText("Вывод менеджера пакетов появится здесь…")
        root.addWidget(self.log, 1)

    def check(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.btn_check.setEnabled(False)
        self.status.setText("Проверяю обновления…")
        self._worker = Worker(st.check_updates)
        self._worker.done.connect(self._check_done)
        self._worker.start()

    def _check_done(self, rows) -> None:
        self._busy = False
        self.btn_check.setEnabled(True)
        self._rows = rows or []
        self.table.setRowCount(len(self._rows))
        for r, p in enumerate(self._rows):
            self.table.setItem(r, 0, _cell(p["name"]))
            self.table.setItem(r, 1, _cell(p["old"] or "—"))
            self.table.setItem(r, 2, _cell(p["new"]))
        self.status.setText(f"Доступно обновлений: {len(self._rows)}")

    def update(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.btn_update.setEnabled(False)
        self.status.setText("Обновляю… (может появиться запрос пароля)")
        self.log.setPlainText("Обновление системы…")
        self._worker = Worker(st.system_update)
        self._worker.done.connect(self._update_done)
        self._worker.start()

    def _update_done(self, result) -> None:
        self._busy = False
        self.btn_update.setEnabled(True)
        if result:
            ok, output = result
            self.log.setPlainText(self.log.toPlainText() + "\n\n" + (output or ""))
            self.status.setText("Готово" if ok else "Ошибка (см. вывод)")
        self.check()


# =========================================================================== #
class PkgFilesPage(QWidget):
    """Файлы пакета и владелец файла (Linux: pacman/dpkg/rpm/apk — по системе)."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._busy = False
        _cat, name, desc = help_for("pkgfiles")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(PageHeader(name, desc))

        bar = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("имя пакета или путь к файлу…")
        self.query.returnPressed.connect(lambda: self.run("files"))
        bar.addWidget(self.query, 1)
        self.mode = QComboBox()
        self.mode.addItem("Файлы пакета", "files")
        self.mode.addItem("Владелец файла", "owner")
        self.mode.addItem("Информация о пакете", "info")
        bar.addWidget(self.mode)
        b = QPushButton("Показать")
        b.setObjectName("Accent")
        b.clicked.connect(lambda: self.run(self.mode.currentData()))
        bar.addWidget(b)
        root.addLayout(bar)

        self.view = _mono("")
        root.addWidget(self.view, 1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        root.addWidget(self.status)

    def run(self, mode: str) -> None:
        if self._busy:
            return
        text = self.query.text().strip()
        if not text:
            self.status.setText("Укажи пакет или путь к файлу")
            return
        self._busy = True
        self.status.setText("Запрашиваю данные пакета…")
        if mode == "files":
            fn = lambda: st.package_files(text)  # noqa: E731
        elif mode == "owner":
            fn = lambda: st.file_owner(text)  # noqa: E731
        else:
            fn = lambda: st.package_info(text)  # noqa: E731
        self._worker = Worker(fn)
        self._worker.done.connect(self._done)
        self._worker.start()

    def _done(self, text) -> None:
        self._busy = False
        self.view.setPlainText(text or "Нет данных")
        self.status.setText("Готово")


# =========================================================================== #
class PortsPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(title("Порты"))
        root.addWidget(dim("Прослушиваемые порты и активные соединения (ss)"))

        bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.refresh)
        bar.addWidget(self.btn_refresh)
        bar.addStretch(1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        bar.addWidget(self.status)
        root.addLayout(bar)

        self.table = table(["Протокол", "Состояние", "Адрес:порт", "Процесс"])
        for i in range(3):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        root.addWidget(self.table, 1)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self) -> None:
        rows = st.listening_ports()
        self.table.setRowCount(len(rows))
        for r, p in enumerate(rows):
            for c, text in enumerate([p["proto"], p["state"], p["local"], p["proc"]]):
                self.table.setItem(r, c, _cell(text))
        self.status.setText(f"Слушают порты: {len(rows)}")


# =========================================================================== #
class HardwarePage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(title("Железо"))
        root.addWidget(dim("Процессор, устройства PCI/USB, накопители и память"))

        bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.refresh)
        bar.addWidget(self.btn_refresh)
        bar.addStretch(1)
        root.addLayout(bar)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self) -> None:
        self.tabs.clear()
        for name, text in st.hardware_sections():
            self.tabs.addTab(_mono(text), name)


# =========================================================================== #
class DiagnosticsPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(title("Диагностика"))
        root.addWidget(dim("Упавшие службы, ошибки в журнале, TRIM"))

        bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Проверить")
        self.btn_refresh.setObjectName("Accent")
        self.btn_refresh.clicked.connect(self.refresh)
        bar.addWidget(self.btn_refresh)
        bar.addStretch(1)
        root.addLayout(bar)

        self.holder = QVBoxLayout()
        root.addLayout(self.holder, 1)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self) -> None:
        while self.holder.count():
            item = self.holder.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
        for name, text in st.diagnostics():
            c = card()
            lay = QVBoxLayout(c)
            lay.setContentsMargins(16, 12, 16, 12)
            lbl = QLabel(name)
            lbl.setObjectName("CardTitle")
            lay.addWidget(lbl)
            edit = _mono(text)
            edit.setMaximumHeight(140)
            lay.addWidget(edit)
            self.holder.addWidget(c)
        self.holder.addStretch(1)


# =========================================================================== #
class TweaksPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        root.addWidget(title("Твики системы"))
        root.addWidget(dim("Настройка swappiness, режима ЦП и просмотр состояния подкачки"))

        c1 = card()
        l1 = QHBoxLayout(c1)
        l1.setContentsMargins(18, 16, 18, 16)
        l1.addWidget(QLabel("vm.swappiness"))
        self.swap = QSpinBox()
        self.swap.setRange(0, 100)
        l1.addWidget(self.swap)
        b1 = QPushButton("Применить")
        b1.clicked.connect(self._apply_swappiness)
        self.btn_swap = b1
        l1.addWidget(b1)
        l1.addStretch(1)
        self.lbl_swap = QLabel("")
        self.lbl_swap.setObjectName("Dim")
        l1.addWidget(self.lbl_swap)
        root.addWidget(c1)

        c2 = card()
        l2 = QHBoxLayout(c2)
        l2.setContentsMargins(18, 16, 18, 16)
        l2.addWidget(QLabel("Режим ЦП (governor)"))
        self.gov = QComboBox()
        l2.addWidget(self.gov)
        b2 = QPushButton("Применить")
        b2.clicked.connect(self._apply_governor)
        self.btn_gov = b2
        l2.addWidget(b2)
        l2.addStretch(1)
        self.lbl_gov = QLabel("")
        self.lbl_gov.setObjectName("Dim")
        l2.addWidget(self.lbl_gov)
        root.addWidget(c2)

        c3 = card()
        l3 = QVBoxLayout(c3)
        l3.setContentsMargins(18, 16, 18, 16)
        t = QLabel("Состояние")
        t.setObjectName("CardTitle")
        l3.addWidget(t)
        self.lbl_state = QLabel("")
        self.lbl_state.setObjectName("CardSub")
        self.lbl_state.setWordWrap(True)
        l3.addWidget(self.lbl_state)
        root.addWidget(c3)

        bar = QHBoxLayout()
        b = QPushButton("Обновить")
        b.clicked.connect(self.refresh)
        bar.addWidget(b)
        bar.addStretch(1)
        root.addLayout(bar)
        root.addStretch(1)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self) -> None:
        self.swap.setValue(st.get_swappiness())
        govs = st.cpu_governors()
        self.gov.clear()
        self.gov.addItems(govs or [st.cpu_governor()])
        self.lbl_gov.setText(f"сейчас: {st.cpu_governor()}")
        # на некоторых системах список режимов пуст — менять нечего
        if govs:
            mark_available(self.gov)
            mark_available(self.btn_gov)
        else:
            mark_unavailable(self.gov)
            mark_unavailable(self.btn_gov)
        self.lbl_state.setText(
            f"<b>Transparent Huge Pages:</b> {st.thp_status()}<br>"
            f"<b>zram / swap:</b> {st.zram_status()}")

    def _apply_swappiness(self) -> None:
        ok = st.set_swappiness(self.swap.value())
        self.lbl_swap.setText("применено" if ok else "нужны права root")

    def _apply_governor(self) -> None:
        ok = st.set_cpu_governor(self.gov.currentText())
        self.lbl_gov.setText(f"сейчас: {st.cpu_governor()}" if ok else "нужны права root")


# =========================================================================== #
class NotesPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(title("Заметки"))
        root.addWidget(dim("Быстрые заметки — сохраняются в домашнем каталоге"))

        self.edit = QPlainTextEdit(st.load_notes())
        self.edit.setPlaceholderText("Пиши здесь…")
        root.addWidget(self.edit, 1)

        bar = QHBoxLayout()
        b = QPushButton("Сохранить")
        b.setObjectName("Accent")
        b.clicked.connect(self.save)
        bar.addWidget(b)
        bar.addStretch(1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        bar.addWidget(self.status)
        root.addLayout(bar)

    def save(self) -> None:
        ok = st.save_notes(self.edit.toPlainText())
        self.status.setText("Сохранено" if ok else "Не удалось сохранить")


# =========================================================================== #
class PasswordPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        root.addWidget(title("Генератор паролей"))
        root.addWidget(dim("Криптостойкие пароли (модуль secrets)"))

        c = card()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        row = QHBoxLayout()
        row.addWidget(QLabel("Длина"))
        self.length = QSpinBox()
        self.length.setRange(4, 128)
        self.length.setValue(20)
        row.addWidget(self.length)
        row.addStretch(1)
        lay.addLayout(row)

        opts = QHBoxLayout()
        self.c_lower = QCheckBox("строчные")
        self.c_upper = QCheckBox("ЗАГЛАВНЫЕ")
        self.c_digits = QCheckBox("цифры")
        self.c_symbols = QCheckBox("символы")
        for cb in (self.c_lower, self.c_upper, self.c_digits, self.c_symbols):
            cb.setChecked(True)
            opts.addWidget(cb)
        opts.addStretch(1)
        lay.addLayout(opts)

        b = QPushButton("Сгенерировать")
        b.setObjectName("Accent")
        b.clicked.connect(self.generate)
        lay.addWidget(b)

        self.output = QLineEdit()
        self.output.setFont(MONO)
        self.output.setReadOnly(True)
        lay.addWidget(self.output)

        row2 = QHBoxLayout()
        self.strength = QLabel("")
        self.strength.setObjectName("Dim")
        row2.addWidget(self.strength)
        row2.addStretch(1)
        copy = QPushButton("Копировать")
        copy.clicked.connect(self._copy)
        row2.addWidget(copy)
        lay.addLayout(row2)
        root.addWidget(c)
        root.addStretch(1)
        self.generate()

    def generate(self) -> None:
        alphabet = ""
        if self.c_lower.isChecked():
            alphabet += string.ascii_lowercase
        if self.c_upper.isChecked():
            alphabet += string.ascii_uppercase
        if self.c_digits.isChecked():
            alphabet += string.digits
        if self.c_symbols.isChecked():
            alphabet += "!@#$%^&*()-_=+[]{};:,.?/"
        if not alphabet:
            alphabet = string.ascii_letters
        length = self.length.value()
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        self.output.setText(pwd)
        import math
        bits = length * math.log2(len(alphabet))
        if bits < 50:
            level = "слабый"
        elif bits < 80:
            level = "средний"
        elif bits < 120:
            level = "надёжный"
        else:
            level = "очень надёжный"
        self.strength.setText(f"Энтропия: ~{bits:.0f} бит — {level}")

    def _copy(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.output.text())
        self.strength.setText("Скопировано в буфер обмена")


# =========================================================================== #
#  Универсальная страница с моноширинным выводом
# =========================================================================== #
class _MonospacePage(QWidget):
    def __init__(self, settings, key: str, loader, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.loader = loader
        self._busy = False
        _cat, name, desc = help_for(key)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(PageHeader(name, desc))
        bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.refresh)
        bar.addWidget(self.btn_refresh)
        self.extra_bar = bar
        bar.addStretch(1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        bar.addWidget(self.status)
        root.addLayout(bar)
        self.view = _mono("")
        root.addWidget(self.view, 1)

    def showEvent(self, e):
        super().showEvent(e)
        if not self.view.toPlainText():
            self.refresh()

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.btn_refresh.setEnabled(False)
        self.status.setText("Загружаю…")
        self._worker = Worker(self.loader)
        self._worker.done.connect(self._done)
        self._worker.start()

    def _done(self, result) -> None:
        self._busy = False
        self.btn_refresh.setEnabled(True)
        if isinstance(result, str):
            self.view.setPlainText(result)
        elif result:
            self.view.setPlainText(
                "\n\n".join(f"=== {n} ===\n{t}" for n, t in result))
        else:
            self.view.setPlainText("Нет данных")
        self.status.setText("Готово")


class BootPage(_MonospacePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, "boot", st.boot_analysis, parent)


class TimersPage(_MonospacePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, "timers", st.list_timers_raw, parent)


# =========================================================================== #
class FirewallPage(_MonospacePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, "firewall", st.firewall_status, parent)
        self.btn_root = QPushButton("Проверить с правами администратора")
        self.btn_root.setToolTip("Запустит проверку с повышенными правами "
                                 "(появится системный запрос пароля)")
        self.btn_root.clicked.connect(self._root_check)
        self.extra_bar.insertWidget(1, self.btn_root)

    def _root_check(self) -> None:
        self.status.setText("Запрашиваю повышенные права…")
        self.loader = st.firewall_status_root
        self.refresh()


# =========================================================================== #
class DisksPage(_MonospacePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, "disks", st.disks_overview, parent)
        self.btn_smart = QPushButton("Проверить SMART")
        self.btn_smart.setToolTip("Здоровье накопителей через smartctl (нужен root)")
        self.btn_smart.clicked.connect(self._smart)
        self.extra_bar.insertWidget(1, self.btn_smart)

    def _smart(self) -> None:
        self.status.setText("Читаю SMART (появится запрос пароля)…")
        self.loader = st.smart_health
        self.refresh()


# =========================================================================== #
class JournalPage(QWidget):
    PRIORITIES = [("Ошибки", "err"), ("Предупреждения", "warning"),
                  ("Информация", "info"), ("Всё", "debug")]

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._busy = False
        _cat, name, desc = help_for("journal")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(PageHeader(name, desc))

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Важность"))
        self.prio = QComboBox()
        for label, value in self.PRIORITIES:
            self.prio.addItem(label, value)
        bar.addWidget(self.prio)
        bar.addWidget(QLabel("Служба"))
        self.unit = QLineEdit()
        self.unit.setPlaceholderText("например: NetworkManager (пусто — все)")
        bar.addWidget(self.unit, 1)
        bar.addWidget(QLabel("Строк"))
        self.lines = QSpinBox()
        self.lines.setRange(50, 5000)
        self.lines.setSingleStep(50)
        self.lines.setValue(self.settings.get_int("journal/lines"))
        bar.addWidget(self.lines)
        self.btn = QPushButton("Показать")
        self.btn.setObjectName("Accent")
        self.btn.clicked.connect(self.refresh)
        bar.addWidget(self.btn)
        root.addLayout(bar)

        self.view = _mono("")
        root.addWidget(self.view, 1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        root.addWidget(self.status)

    def showEvent(self, e):
        super().showEvent(e)
        if not self.view.toPlainText():
            self.refresh()

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.btn.setEnabled(False)
        self.settings.set("journal/lines", self.lines.value())
        prio = self.prio.currentData()
        unit = self.unit.text().strip()
        lines = self.lines.value()
        self.status.setText("Читаю журнал…")
        self._worker = Worker(lambda: st.journal_entries(prio, lines, unit))
        self._worker.done.connect(self._done)
        self._worker.start()

    def _done(self, text) -> None:
        self._busy = False
        self.btn.setEnabled(True)
        self.view.setPlainText(text or "Записей нет")
        self.status.setText("Готово")


# =========================================================================== #
class ModulesPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._rows: list[dict] = []
        self._busy = False
        _cat, name, desc = help_for("modules")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(PageHeader(name, desc))

        bar = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Фильтр по имени модуля…")
        self.filter.textChanged.connect(self._apply_filter)
        bar.addWidget(self.filter, 1)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("имя модуля")
        bar.addWidget(self.name_input)
        self.btn_load = QPushButton("Загрузить")
        self.btn_load.clicked.connect(lambda: self._action("load"))
        bar.addWidget(self.btn_load)
        self.btn_unload = QPushButton("Выгрузить выбранный")
        self.btn_unload.setObjectName("Danger")
        self.btn_unload.clicked.connect(lambda: self._action("unload"))
        bar.addWidget(self.btn_unload)
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.refresh)
        bar.addWidget(self.btn_refresh)
        root.addLayout(bar)

        self.table = table(["Модуль", "Размер", "Использований", "Кем используется"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        root.addWidget(self.table, 1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        root.addWidget(self.status)

    def showEvent(self, e):
        super().showEvent(e)
        if not self._rows:
            self.refresh()

    def refresh(self) -> None:
        self._rows = st.list_modules()
        self.table.setRowCount(len(self._rows))
        for r, m in enumerate(self._rows):
            for c, text in enumerate([m["name"], m["size"], m["used"], m["by"]]):
                self.table.setItem(r, c, _cell(text))
        self._apply_filter(self.filter.text())
        self.status.setText(f"Модулей: {len(self._rows)}")
        # модули ядра есть только на Linux; иначе функции недоступны
        if self._rows:
            for w in (self.name_input, self.btn_load, self.btn_unload):
                mark_available(w)
        else:
            for w in (self.name_input, self.btn_load, self.btn_unload):
                mark_unavailable(w)

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for r, m in enumerate(self._rows):
            self.table.setRowHidden(r, bool(needle) and needle not in m["name"].lower())

    def _action(self, action: str) -> None:
        if self._busy:
            return
        if action == "load":
            name = self.name_input.text().strip()
        else:
            row = self.table.currentRow()
            name = self.table.item(row, 0).text() if row >= 0 else ""
        if not name:
            self.status.setText("Укажи модуль (введи имя или выбери строку)")
            return
        self._busy = True
        self.status.setText(f"{'Загружаю' if action == 'load' else 'Выгружаю'} {name}…")
        self._worker = Worker(lambda: st.module_action(name, action))
        self._worker.done.connect(self._action_done)
        self._worker.start()

    def _action_done(self, result) -> None:
        self._busy = False
        if result:
            ok, msg = result
            self.status.setText(msg)
        self.refresh()


# =========================================================================== #
class TrashPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._rows: list[dict] = []
        _cat, name, desc = help_for("trash")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(PageHeader(name, desc))

        bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.refresh)
        bar.addWidget(self.btn_refresh)
        self.btn_empty = QPushButton("Очистить корзину")
        self.btn_empty.setObjectName("Danger")
        self.btn_empty.clicked.connect(self._empty)
        bar.addWidget(self.btn_empty)
        bar.addStretch(1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        bar.addWidget(self.status)
        root.addLayout(bar)

        self.table = table(["Файл", "Исходный путь", "Удалён"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        root.addWidget(self.table, 1)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self) -> None:
        self._rows = st.trash_items()
        self.table.setRowCount(len(self._rows))
        for r, it in enumerate(self._rows):
            for c, text in enumerate([it["name"], it["path"], it["date"]]):
                self.table.setItem(r, c, _cell(text))
        self.status.setText(f"Файлов в корзине: {len(self._rows)}")

    def _empty(self) -> None:
        if not self._rows:
            self.status.setText("Корзина уже пуста")
            return
        ans = QMessageBox.question(
            self, "Очистка корзины",
            f"Удалить безвозвратно {len(self._rows)} файл(ов)?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        _ok, msg = st.empty_trash()
        self.status.setText(msg)
        self.refresh()


# =========================================================================== #
class HashPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._busy = False
        _cat, name, desc = help_for("hashes")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(PageHeader(name, desc))

        tabs = QTabWidget()
        root.addWidget(tabs, 1)
        tabs.addTab(self._file_tab(), "Файл")
        tabs.addTab(self._text_tab(), "Текст")
        tabs.addTab(self._verify_tab(), "Проверка")

    def _algo_combo(self) -> QComboBox:
        box = QComboBox()
        box.addItems(st.ALGOS)
        box.setCurrentText("sha256")
        return box

    def _file_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        row = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("путь к файлу…")
        row.addWidget(self.file_path, 1)
        b = QPushButton("Выбрать…")
        b.clicked.connect(self._pick_file)
        row.addWidget(b)
        self.file_algo = self._algo_combo()
        row.addWidget(self.file_algo)
        run_btn = QPushButton("Посчитать")
        run_btn.setObjectName("Accent")
        run_btn.clicked.connect(self._hash_file)
        row.addWidget(run_btn)
        lay.addLayout(row)
        self.file_out = _mono("")
        lay.addWidget(self.file_out, 1)
        return w

    def _text_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        self.text_in = QPlainTextEdit()
        self.text_in.setPlaceholderText("Текст для хэширования…")
        lay.addWidget(self.text_in, 1)
        row = QHBoxLayout()
        self.text_algo = self._algo_combo()
        row.addWidget(self.text_algo)
        b = QPushButton("Посчитать")
        b.setObjectName("Accent")
        b.clicked.connect(self._hash_text)
        row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.text_out = QLineEdit()
        self.text_out.setFont(MONO)
        self.text_out.setReadOnly(True)
        lay.addWidget(self.text_out)
        return w

    def _verify_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        row = QHBoxLayout()
        self.verify_path = QLineEdit()
        self.verify_path.setPlaceholderText("путь к файлу…")
        row.addWidget(self.verify_path, 1)
        b = QPushButton("Выбрать…")
        b.clicked.connect(lambda: self._pick_into(self.verify_path))
        row.addWidget(b)
        lay.addLayout(row)
        row2 = QHBoxLayout()
        self.verify_expected = QLineEdit()
        self.verify_expected.setPlaceholderText("ожидаемый хэш…")
        self.verify_expected.setFont(MONO)
        row2.addWidget(self.verify_expected, 1)
        self.verify_algo = self._algo_combo()
        row2.addWidget(self.verify_algo)
        b2 = QPushButton("Проверить")
        b2.setObjectName("Accent")
        b2.clicked.connect(self._verify)
        row2.addWidget(b2)
        lay.addLayout(row2)
        self.verify_out = QLabel("")
        self.verify_out.setObjectName("CardTitle")
        self.verify_out.setWordWrap(True)
        lay.addWidget(self.verify_out)
        lay.addStretch(1)
        return w

    def _pick_file(self) -> None:
        self._pick_into(self.file_path)

    def _pick_into(self, target: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать файл")
        if path:
            target.setText(path)

    def _hash_file(self) -> None:
        path = self.file_path.text().strip()
        if not path:
            self.file_out.setPlainText("Укажи путь к файлу")
            return
        algo = self.file_algo.currentText()
        self.file_out.setPlainText("Считаю…")
        self._worker = Worker(lambda: f"{algo}: {st.hash_file(path, algo)}")
        self._worker.done.connect(lambda r: self.file_out.setPlainText(r or "Ошибка"))
        self._worker.start()

    def _hash_text(self) -> None:
        algo = self.text_algo.currentText()
        self.text_out.setText(st.hash_text(self.text_in.toPlainText(), algo))

    def _verify(self) -> None:
        path = self.verify_path.text().strip()
        expected = self.verify_expected.text().strip()
        algo = self.verify_algo.currentText()
        if not path or not expected:
            self.verify_out.setText("Укажи файл и ожидаемый хэш")
            return
        self.verify_out.setText("Проверяю…")
        self._worker = Worker(lambda: st.verify_hash(path, expected, algo))
        self._worker.done.connect(self._verify_done)
        self._worker.start()

    def _verify_done(self, ok) -> None:
        if ok:
            self.verify_out.setText("Хэши совпадают — файл целый")
        else:
            self.verify_out.setText("Хэши НЕ совпадают — файл повреждён или изменён")


# =========================================================================== #
class TextToolsPage(QWidget):
    MODES = [("Base64 в текст", "base64d"), ("текст в Base64", "base64e"),
             ("URL-декодировать", "urld"), ("URL-кодировать", "urle"),
             ("Формат JSON", "json"), ("JSON в строку", "jsonmin"),
             ("В ВЕРХНИЙ регистр", "upper"), ("в нижний регистр", "lower"),
             ("Реверс текста", "reverse"), ("Убрать отступы", "strip"),
             ("Отсортировать строки", "sort"), ("Подсчёт символов", "count")]

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        _cat, name, desc = help_for("texttools")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(PageHeader(name, desc))

        bar = QHBoxLayout()
        self.mode = QComboBox()
        for label, value in self.MODES:
            self.mode.addItem(label, value)
        bar.addWidget(self.mode)
        b = QPushButton("Преобразовать")
        b.setObjectName("Accent")
        b.clicked.connect(self.convert)
        bar.addWidget(b)
        b2 = QPushButton("Копировать результат")
        b2.clicked.connect(self._copy)
        bar.addWidget(b2)
        b3 = QPushButton("Поменять местами")
        b3.clicked.connect(self._swap)
        bar.addWidget(b3)
        bar.addStretch(1)
        root.addLayout(bar)

        panes = QHBoxLayout()
        self.src = QPlainTextEdit()
        self.src.setPlaceholderText("Исходный текст…")
        self.dst = QPlainTextEdit()
        self.dst.setPlaceholderText("Результат…")
        self.dst.setReadOnly(True)
        panes.addWidget(self.src)
        panes.addWidget(self.dst)
        root.addLayout(panes, 1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        root.addWidget(self.status)

    def convert(self) -> None:
        mode = self.mode.currentData()
        self.dst.setPlainText(st.text_transform(mode, self.src.toPlainText()))
        self.status.setText("Готово")

    def _copy(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.dst.toPlainText())
        self.status.setText("Результат скопирован")

    def _swap(self) -> None:
        self.src.setPlainText(self.dst.toPlainText())
        self.dst.clear()


# =========================================================================== #
class BackupPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._busy = False
        _cat, name, desc = help_for("backup")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(PageHeader(name, desc))

        c = card()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Откуда"))
        self.src = QLineEdit(self.settings.get("backup/src"))
        self.src.setPlaceholderText("папка-источник…")
        row1.addWidget(self.src, 1)
        b1 = QPushButton("Выбрать…")
        b1.clicked.connect(lambda: self._pick(self.src))
        row1.addWidget(b1)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Куда"))
        self.dst = QLineEdit(self.settings.get("backup/dst"))
        self.dst.setPlaceholderText("папка-назначение…")
        row2.addWidget(self.dst, 1)
        b2 = QPushButton("Выбрать…")
        b2.clicked.connect(lambda: self._pick(self.dst))
        row2.addWidget(b2)
        lay.addLayout(row2)

        row3 = QHBoxLayout()
        self.mirror = QCheckBox("Зеркалить (удалять в приёмнике то, чего нет в источнике)")
        row3.addWidget(self.mirror)
        row3.addStretch(1)
        self.btn_run = QPushButton("Запустить копирование")
        self.btn_run.setObjectName("Accent")
        self.btn_run.clicked.connect(self.run)
        row3.addWidget(self.btn_run)
        lay.addLayout(row3)
        root.addWidget(c)

        self.log = _mono("")
        self.log.setPlaceholderText("Вывод копирования появится здесь…")
        root.addWidget(self.log, 1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        root.addWidget(self.status)

    def _pick(self, target: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Выбрать папку")
        if path:
            target.setText(path)

    def run(self) -> None:
        if self._busy:
            return
        src = self.src.text().strip()
        dst = self.dst.text().strip()
        if not src or not dst:
            self.status.setText("Укажи источник и назначение")
            return
        self.settings.set("backup/src", src)
        self.settings.set("backup/dst", dst)
        self._busy = True
        self.btn_run.setEnabled(False)
        self.status.setText("Копирую…")
        self.log.setPlainText(f"Копирование: {src}  ->  {dst}")
        mirror = self.mirror.isChecked()
        self._worker = Worker(lambda: st.run_rsync(src, dst, mirror))
        self._worker.done.connect(self._done)
        self._worker.start()

    def _done(self, result) -> None:
        self._busy = False
        self.btn_run.setEnabled(True)
        if result:
            ok, output = result
            self.log.setPlainText(self.log.toPlainText() + "\n\n" + (output or ""))
            self.status.setText("Готово" if ok else "Ошибка (см. вывод)")


# =========================================================================== #
class HelpPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        from .helptext import PAGE_HELP
        from .main_window import NAV

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(PageHeader(
            "Справка",
            "Каталог функций: что делает каждый раздел. Подсказки также "
            "появляются при наведении на пункты меню слева."))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        col = QVBoxLayout(holder)
        col.setContentsMargins(0, 0, 6, 0)
        col.setSpacing(14)

        for section, items in NAV:
            c = card()
            lay = QVBoxLayout(c)
            lay.setContentsMargins(18, 16, 18, 16)
            lay.setSpacing(8)
            head = QLabel(section)
            head.setObjectName("CardTitle")
            lay.addWidget(head)
            for _label, key in items:
                _cat, name, desc = PAGE_HELP.get(key, ("", key, ""))
                item = QLabel(f"<b>{name}</b> — {desc}")
                item.setWordWrap(True)
                item.setTextFormat(Qt.RichText)
                item.setObjectName("CardSub")
                lay.addWidget(item)
            col.addWidget(c)
        col.addStretch(1)
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

