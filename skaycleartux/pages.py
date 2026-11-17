"""Экраны SkayClearTux: главная, очистка, анализ диска, темы, о программе."""
from __future__ import annotations

import os
import platform
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QMessageBox, QProgressBar, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from . import cleaner
from . import system_tools as st
from . import themes as themes_mod
from . import __version__
from .resources import asset
from .settings import CREATOR


def card() -> QFrame:
    f = QFrame()
    f.setObjectName("Card")
    return f


def human(n: float) -> str:
    return cleaner.human(n)


# --------------------------------------------------------------------------- #
class Worker(QThread):
    progress = Signal(str)
    done = Signal(object)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self) -> None:
        try:
            self.done.emit(self.fn())
        except Exception as e:  # noqa: BLE001
            self.progress.emit(f"Ошибка: {e}")
            self.done.emit(None)


# --------------------------------------------------------------------------- #
class SystemInfo:
    """Совместимая обёртка над системным бэкендом (Linux / macOS / Windows)."""

    def cpu_percent(self) -> float:
        return st.cpu_percent()

    @staticmethod
    def mem() -> tuple[float, float]:
        return st.memory_info()

    @staticmethod
    def uptime() -> str:
        return st.uptime()

    @staticmethod
    def os_name() -> str:
        return st.os_pretty_name()

    @staticmethod
    def cpu_model() -> str:
        return st.cpu_model()


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.info = SystemInfo()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        head = QLabel("Главная")
        head.setObjectName("H1")
        root.addWidget(head)
        root.addWidget(self._dim("Обзор системы и быстрые действия"))

        grid = QGridLayout()
        grid.setSpacing(14)
        self.m_cpu = self._metric(grid, 0, 0, "Загрузка ЦП", "0 %")
        self.m_ram = self._metric(grid, 0, 1, "Оперативная память", "0 / 0 ГБ")
        self.m_disk = self._metric(grid, 1, 0, "Свободно на диске", "0 ГБ")
        self.m_up = self._metric(grid, 1, 1, "Время работы", "—")
        self.m_temp = self._metric(grid, 2, 0, "Температура ЦП", "—")
        self.m_bat = self._metric(grid, 2, 1, "Батарея", "—")
        root.addLayout(grid)

        info = card()
        il = QVBoxLayout(info)
        il.setContentsMargins(18, 16, 18, 16)
        t = QLabel("Система"); t.setObjectName("CardTitle"); il.addWidget(t)
        self.sys_label = QLabel(); self.sys_label.setObjectName("CardSub")
        self.sys_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        il.addWidget(self.sys_label)
        root.addWidget(info)
        root.addStretch(1)

        self._refresh_static()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_live)
        self.timer.start(2000)
        self._refresh_live()

    @staticmethod
    def _dim(text: str) -> QLabel:
        l = QLabel(text); l.setObjectName("Dim"); return l

    def _metric(self, grid, r, c, label, value) -> QLabel:
        c1 = card()
        lay = QVBoxLayout(c1); lay.setContentsMargins(18, 16, 18, 16)
        v = QLabel(value); v.setObjectName("Metric")
        l = QLabel(label); l.setObjectName("MetricLabel")
        lay.addWidget(v); lay.addWidget(l)
        grid.addWidget(c1, r, c)
        return v

    def _refresh_static(self) -> None:
        cores = os.cpu_count()
        self.sys_label.setText(
            f"<b>ОС:</b> {self.info.os_name()}<br>"
            f"<b>Ядро:</b> {platform.release()}<br>"
            f"<b>Процессор:</b> {self.info.cpu_model()} ({cores} потоков)<br>"
            f"<b>Хост:</b> {platform.node()}")

    def _refresh_live(self) -> None:
        if self.isVisible() and not self.window().isActiveWindow():
            return
        try:
            cpu = self.info.cpu_percent()
            total, used = self.info.mem()
            _total_b, free_b, percent = st.disk_usage()
            self.m_cpu.setText(f"{cpu:.0f} %")
            self.m_ram.setText(f"{used:.1f} / {total:.1f} ГБ")
            self.m_disk.setText(f"{cleaner.human(free_b)} свободно")
            self.m_disk.setToolTip(f"Занято {percent}%")
            self.m_up.setText(self.info.uptime())
            temps, _fans = st.sensors_info()
            self.m_temp.setText(f"{max(t for _n, t in temps):.0f} °C"
                                if temps else "—")
            bat = st.battery_info()
            if bat:
                self.m_bat.setText(f"{bat.get('capacity', '—')} %")
                self.m_bat.setToolTip(f"{bat.get('status', '')}")
            else:
                self.m_bat.setText("—")
        except Exception:  # noqa: BLE001 — не даём дашборду уронить программу
            pass


# --------------------------------------------------------------------------- #
class CategoryRow(QWidget):
    def __init__(self, cat: cleaner.Category, checked: bool = True, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(12)
        self.check = QCheckBox()
        self.check.setChecked(checked)
        lay.addWidget(self.check)
        color = {"безопасно": "#4ade80", "внимание": "#f5c542", "опасно": "#ff6b81"}[cat.risk_ru]
        dot = QFrame()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(f"background:{color}; border-radius:5px;")
        dot.setToolTip(cat.risk_ru)
        lay.addWidget(dot)
        txt = QVBoxLayout(); txt.setSpacing(2)
        self.title = QLabel(cat.title); self.title.setObjectName("CardTitle")
        self.detail = QLabel(cat.detail); self.detail.setObjectName("CardSub")
        self.detail.setWordWrap(True)
        txt.addWidget(self.title); txt.addWidget(self.detail)
        lay.addLayout(txt, 1)
        badge = QLabel(cat.risk_ru)
        color = {"безопасно": "#4ade80", "внимание": "#f5c542", "опасно": "#ff6b81"}[cat.risk_ru]
        badge.setStyleSheet(f"color:{color}; font-weight:700; font-size:12px;")
        lay.addWidget(badge)
        self.size = QLabel(human(cat.size))
        self.size.setStyleSheet("font-weight:800; font-size:15px;")
        self.size.setFixedWidth(90)
        self.size.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self.size)
        self.cat = cat


class CleanerPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.rows: list[CategoryRow] = []
        self._scanned = False
        self._worker = None
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)

        head = QLabel("Очистка системы")
        head.setObjectName("H1")
        root.addWidget(head)
        root.addWidget(self._dim("Скан ничего не удаляет. Чистка — только после подтверждения."))

        top = QHBoxLayout()
        self.disk_bar = QProgressBar()
        self.disk_label = QLabel("")
        top.addWidget(self.disk_label)
        top.addStretch(1)
        self.btn_scan = QPushButton("Сканировать")
        self.btn_scan.clicked.connect(self.scan)
        top.addWidget(self.btn_scan)
        root.addLayout(top)

        self.total_label = QLabel("Нажмите «Сканировать»")
        self.total_label.setObjectName("H2")
        root.addWidget(self.total_label)

        sel = QHBoxLayout()
        for text, fn in [("Выбрать безопасные", self.select_safe),
                         ("Выбрать все", self.select_all),
                         ("Снять всё", self.select_none)]:
            b = QPushButton(text); b.clicked.connect(fn); sel.addWidget(b)
        sel.addStretch(1)
        self.btn_clean = QPushButton("Очистить выбранное")
        self.btn_clean.setObjectName("Accent")
        self.btn_clean.clicked.connect(self.clean)
        sel.addWidget(self.btn_clean)
        root.addLayout(sel)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.holder = QWidget(); self.vbox = QVBoxLayout(self.holder)
        self.vbox.setContentsMargins(0, 0, 0, 0); self.vbox.setSpacing(4)
        self.vbox.addStretch(1)
        self.scroll.setWidget(self.holder)
        root.addWidget(self.scroll, 1)

        self.status = QLabel(""); self.status.setObjectName("Dim")
        root.addWidget(self.status)

    @staticmethod
    def _dim(t):
        l = QLabel(t); l.setObjectName("Dim"); return l

    def _fill_rows(self, cats) -> None:
        for row in self.rows:
            row.setParent(None)
        self.rows.clear()
        select_safe = self.settings.get_bool("cleaner/select_safe")
        for c in cats:
            row = CategoryRow(c, checked=(c.safe if select_safe else False))
            self.rows.append(row)
            self.vbox.insertWidget(self.vbox.count() - 1, row)
        self._update_total()

    def _update_total(self) -> None:
        total = sum(r.cat.size for r in self.rows if r.check.isChecked())
        self.total_label.setText(f"Выбрано к очистке: {human(total)}")

    def select_safe(self):
        for r in self.rows:
            r.check.setChecked(r.cat.safe)
        self._update_total()

    def select_all(self):
        for r in self.rows:
            r.check.setChecked(True)
        self._update_total()

    def select_none(self):
        for r in self.rows:
            r.check.setChecked(False)
        self._update_total()

    def showEvent(self, e):
        super().showEvent(e)
        if not self._scanned:
            self._scanned = True
            self.scan()

    def scan(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        self.btn_scan.setEnabled(False)
        self.status.setText("Сканирую… (это может занять немного времени)")
        self._worker = Worker(cleaner.scan_all)
        self._worker.done.connect(self._scan_done)
        self._worker.start()

    def _scan_done(self, cats) -> None:
        self.btn_scan.setEnabled(True)
        if cats:
            self._fill_rows(cats)
        dfree, dtotal, dpercent = cleaner.disk_free()
        root_name = "/" if os.name == "posix" else (os.environ.get("SystemDrive", "C:") + "\\")
        self.disk_label.setText(
            f"Диск {root_name}: занято {dpercent}%  ·  свободно {dfree} из {dtotal}")
        self.status.setText("Сканирование завершено.")

    def clean(self) -> None:
        chosen = [r.cat for r in self.rows if r.check.isChecked()]
        if not chosen:
            QMessageBox.information(self, "Нечего чистить", "Выбери хотя бы одну категорию.")
            return
        total = sum(c.size for c in chosen)
        names = "\n".join(f"• {c.title} — {human(c.size)}" for c in chosen)
        if self.settings.get_bool("cleaner/confirm"):
            ok = QMessageBox.question(
                self, "Подтверждение",
                f"Будет очищено (~{human(total)}):\n\n{names}\n\nПродолжить?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ok != QMessageBox.Yes:
                return
        self.btn_clean.setEnabled(False)
        self.status.setText("Чищу… (для системных категорий появится запрос пароля)")

        def job():
            results = []
            for c in chosen:
                try:
                    freed, msg = c.clean()
                except Exception as e:  # noqa: BLE001
                    freed, msg = 0, f"ошибка: {e}"
                results.append((c.title, freed, msg))
            return results

        self._worker = Worker(job)
        self._worker.done.connect(self._clean_done)
        self._worker.start()

    def _clean_done(self, results) -> None:
        self.btn_clean.setEnabled(True)
        if not results:
            self.status.setText("Чистка прервана.")
            return
        freed = sum(r[1] for r in results)
        detail = "\n".join(f"• {t}: {human(f)}" if f else f"• {t}: —" for t, f, _ in results)
        QMessageBox.information(self, "Готово", f"Освобождено ~{human(freed)}\n\n{detail}")
        self._scanned = False
        self.scan()


# --------------------------------------------------------------------------- #
class DiskPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        head = QLabel("Анализ диска")
        head.setObjectName("H1")
        root.addWidget(head)
        root.addWidget(self._dim("Самые крупные папки в домашнем каталоге"))

        row = QHBoxLayout()
        self.btn = QPushButton("Проанализировать")
        self.btn.clicked.connect(self.scan)
        row.addWidget(self.btn)
        self.path_label = QLabel(str(Path.home())); self.path_label.setObjectName("Dim")
        row.addWidget(self.path_label); row.addStretch(1)
        root.addLayout(row)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.holder = QWidget(); self.vbox = QVBoxLayout(self.holder)
        self.vbox.setContentsMargins(0, 0, 0, 0); self.vbox.setSpacing(6)
        self.scroll.setWidget(self.holder)
        root.addWidget(self.scroll, 1)
        self._scanned = False

    @staticmethod
    def _dim(t):
        l = QLabel(t); l.setObjectName("Dim"); return l

    def showEvent(self, e):
        super().showEvent(e)
        if not self._scanned:
            self._scanned = True
            self.scan()

    def scan(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        self.btn.setEnabled(False)
        home = Path.home()

        def job():
            items = []
            for entry in os.scandir(home):
                if entry.name.startswith("."):
                    continue
                try:
                    size = cleaner.du_bytes(Path(entry.path)) if entry.is_dir() else entry.stat().st_size
                except OSError:
                    continue
                items.append((entry.name, size))
            items.sort(key=lambda x: x[1], reverse=True)
            return items[:30]

        self._worker = Worker(job)
        self._worker.done.connect(self._done)
        self._worker.start()

    def _done(self, items) -> None:
        self.btn.setEnabled(True)
        while self.vbox.count():
            w = self.vbox.takeAt(0).widget()
            if w:
                w.setParent(None)
        if not items:
            self.vbox.addWidget(self._dim("Пусто"))
            return
        mx = max(s for _, s in items) or 1
        for name, size in items:
            row = QWidget()
            lay = QHBoxLayout(row); lay.setContentsMargins(4, 2, 4, 2)
            lab = QLabel(name); lab.setFixedWidth(220)
            bar = QProgressBar(); bar.setRange(0, 1000)
            bar.setValue(int(1000 * size / mx)); bar.setTextVisible(False)
            bar.setFixedHeight(16)
            val = QLabel(human(size)); val.setFixedWidth(90)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lay.addWidget(lab); lay.addWidget(bar, 1); lay.addWidget(val)
            self.vbox.addWidget(row)
        self.vbox.addStretch(1)


# --------------------------------------------------------------------------- #
class ThemesPage(QWidget):
    def __init__(self, on_apply, current: str, parent=None):
        super().__init__(parent)
        self.on_apply = on_apply
        self.current = current
        self.buttons: dict[str, QPushButton] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        head = QLabel("Темы оформления")
        head.setObjectName("H1")
        root.addWidget(head)
        root.addWidget(self._dim("Выбери настроение — применится мгновенно и запомнится"))

        grid = QGridLayout(); grid.setSpacing(14)
        for idx, (name, colors) in enumerate(themes_mod.THEMES.items()):
            grid.addWidget(self._theme_card(name, colors), idx // 3, idx % 3)
        wrap = QWidget(); wrap.setLayout(grid)
        root.addWidget(wrap)
        root.addStretch(1)

    @staticmethod
    def _dim(t):
        l = QLabel(t); l.setObjectName("Dim"); return l

    def _theme_card(self, name: str, colors: dict) -> QFrame:
        c = card()
        lay = QVBoxLayout(c); lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(10)
        title = QLabel(name); title.setObjectName("CardTitle")
        lay.addWidget(title)
        sw = QHBoxLayout(); sw.setSpacing(6)
        for key in ("bg", "card", "accent", "text", "success", "danger"):
            d = QFrame(); d.setFixedSize(26, 26)
            d.setStyleSheet(f"background:{colors[key]}; border-radius:6px; border:1px solid {colors['border']};")
            sw.addWidget(d)
        sw.addStretch(1)
        lay.addLayout(sw)
        btn = QPushButton("Применить")
        btn.clicked.connect(lambda _=False, n=name: self.on_apply(n))
        self.buttons[name] = btn
        self._style_button(btn, name)
        lay.addWidget(btn)
        return c

    @staticmethod
    def _style_button(btn: QPushButton, name: str, active: bool = False) -> None:
        btn.setObjectName("Accent" if active else "")
        btn.style().unpolish(btn)
        btn.style().polish(btn)

    def set_current(self, name: str) -> None:
        """Перерисовать метки активной темы без пересборки страницы."""
        self.current = name
        for theme_name, btn in self.buttons.items():
            self._style_button(btn, theme_name, theme_name == name)


# --------------------------------------------------------------------------- #
class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)
        head = QLabel("О программе")
        head.setObjectName("H1")
        root.addWidget(head)

        c = card()
        lay = QHBoxLayout(c); lay.setContentsMargins(22, 22, 22, 22); lay.setSpacing(22)
        logo = QLabel()
        pix = QPixmap(asset("tux.png"))
        logo.setPixmap(pix.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(logo, 0, Qt.AlignTop)
        text = QVBoxLayout(); text.setSpacing(6)
        name = QLabel("SkayClearTux"); name.setObjectName("H1")
        ver = QLabel(f"Версия {__version__} · Linux · macOS · Windows")
        ver.setObjectName("CardSub")
        desc = QLabel(
            "Универсальный помощник: очистка системы, монитор ресурсов, анализ диска, "
            "диспетчер процессов, службы, пакеты, сеть, датчики, автозапуск, темы "
            "оформления и шахматы с ботом — всё в одном красивом окне.<br><br>"
            f"<b>Создатель:</b> {CREATOR}<br>"
            "<b>Логотип:</b> Tux — официальный талисман Linux.<br>"
            "<b>Технологии:</b> Python 3 · PySide6 (Qt 6) · собственный шахматный движок.<br>"
            "<b>Лицензия:</b> MIT.")
        desc.setWordWrap(True); desc.setTextFormat(Qt.RichText)
        text.addWidget(name); text.addWidget(ver); text.addSpacing(6); text.addWidget(desc)
        text.addStretch(1)
        lay.addLayout(text, 1)
        root.addWidget(c)
        root.addStretch(1)
