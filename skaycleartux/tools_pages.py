"""Инструменты SkayClearTux: процессы, службы, пакеты, сеть, датчики, автозапуск."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from . import system_tools as st
from .cleaner import human
from .pages import Worker


def card() -> QFrame:
    f = QFrame()
    f.setObjectName("Card")
    return f


def dim(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Dim")
    lbl.setWordWrap(True)
    return lbl


def table(columns: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(columns))
    t.setHorizontalHeaderLabels(columns)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(False)
    t.horizontalHeader().setStretchLastSection(True)
    return t


def _cell(text: str, align_right: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    if align_right:
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return item


def _title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("H1")
    return lbl


# =========================================================================== #
class ProcessesPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._busy = False
        self._rows: list[dict] = []
        self._pids: list[int] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(_title("Процессы"))
        root.addWidget(dim("Диспетчер задач: живой список процессов и завершение по сигналу"))

        bar = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Фильтр по имени или команде…")
        self.filter.textChanged.connect(self._apply_filter)
        bar.addWidget(self.filter, 1)
        self.auto = QCheckBox("Автообновление")
        self.auto.setChecked(True)
        self.auto.toggled.connect(self._toggle_auto)
        bar.addWidget(self.auto)
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.refresh)
        bar.addWidget(self.btn_refresh)
        root.addLayout(bar)

        self.table = table(["PID", "Имя", "Пользователь", "ЦП %", "Память %", "Команда"])
        for i in range(5):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.doubleClicked.connect(lambda _i: self._kill(False))
        root.addWidget(self.table, 1)

        act = QHBoxLayout()
        self.btn_term = QPushButton("Завершить (SIGTERM)")
        self.btn_term.clicked.connect(lambda: self._kill(False))
        self.btn_kill = QPushButton("Убить (SIGKILL)")
        self.btn_kill.setObjectName("Danger")
        self.btn_kill.clicked.connect(lambda: self._kill(True))
        act.addWidget(self.btn_term)
        act.addWidget(self.btn_kill)
        act.addStretch(1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        act.addWidget(self.status)
        root.addLayout(act)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._auto_tick)
        self._start_timer()

    def _start_timer(self) -> None:
        self.timer.start(max(1, self.settings.get_int("tools/refresh_sec")) * 1000)

    def _toggle_auto(self, on: bool) -> None:
        if on:
            self._start_timer()
        else:
            self.timer.stop()

    def _auto_tick(self) -> None:
        if self.isVisible() and self.window().isActiveWindow() and not self._busy:
            self.refresh()

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self) -> None:
        rows = st.list_processes()
        if self.settings.get_bool("tools/hide_kernel"):
            rows = [p for p in rows
                    if not (p["cmd"].startswith("[") and p["cmd"].endswith("]"))]
        self._rows = rows
        self._populate()

    def _set(self, r: int, c: int, text: str, align_right: bool = False) -> None:
        item = self.table.item(r, c)
        if item is None:
            item = _cell(text, align_right)
            self.table.setItem(r, c, item)
        elif item.text() != text:
            item.setText(text)

    def _populate(self) -> None:
        pids = [p["pid"] for p in self._rows]
        self.table.setUpdatesEnabled(False)
        try:
            if pids != self._pids:
                self._pids = pids
                self.table.setRowCount(len(self._rows))
                for r, p in enumerate(self._rows):
                    self._set(r, 0, str(p["pid"]), True)
                    self._set(r, 1, p["name"])
                    self._set(r, 2, p["user"])
                    self._set(r, 3, f"{p['cpu']:.1f}", True)
                    self._set(r, 4, f"{p['mem']:.1f}", True)
                    self._set(r, 5, p["cmd"])
            else:
                for r, p in enumerate(self._rows):
                    self._set(r, 3, f"{p['cpu']:.1f}", True)
                    self._set(r, 4, f"{p['mem']:.1f}", True)
        finally:
            self.table.setUpdatesEnabled(True)
        self._apply_filter(self.filter.text())
        self.status.setText(f"Процессов: {len(self._rows)}")

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for r, p in enumerate(self._rows):
            match = (not needle) or needle in p["name"].lower() or needle in p["cmd"].lower()
            self.table.setRowHidden(r, not match)

    def _selected_pid(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    def _kill(self, force: bool) -> None:
        pid = self._selected_pid()
        if pid is None:
            self.status.setText("Сначала выбери процесс в списке")
            return
        if self._busy:
            return
        self._busy = True
        self.status.setText(f"Отправляю сигнал процессу {pid}…")

        def job():
            return st.kill_process(pid, force)

        self._worker = Worker(job)
        self._worker.done.connect(self._kill_done)
        self._worker.start()

    def _kill_done(self, result) -> None:
        self._busy = False
        if result:
            ok, msg = result
            self.status.setText(("Готово: " if ok else "Ошибка: ") + msg)
        self.refresh()


# =========================================================================== #
class ServicesPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._busy = False
        self._rows: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(_title("Службы"))
        root.addWidget(dim("Управление системными службами (systemd — Linux, launchd — "
                           "macOS, службы Windows). Действия могут требовать прав "
                           "администратора."))

        bar = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Фильтр по имени…")
        self.filter.textChanged.connect(self._apply_filter)
        bar.addWidget(self.filter, 1)
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.refresh)
        bar.addWidget(self.btn_refresh)
        root.addLayout(bar)

        self.table = table(["Служба", "Активность", "Состояние", "Описание"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        root.addWidget(self.table, 1)

        act = QHBoxLayout()
        for label, action in (("Старт", "start"), ("Стоп", "stop"),
                              ("Перезапуск", "restart"), ("Включить", "enable"),
                              ("Выключить", "disable")):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, a=action: self._action(a))
            act.addWidget(b)
        act.addStretch(1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        act.addWidget(self.status)
        root.addLayout(act)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self) -> None:
        self._rows = st.list_services()
        self.table.setRowCount(len(self._rows))
        for r, s in enumerate(self._rows):
            for c, text in enumerate([s["unit"], s["active"], s["sub"], s["desc"]]):
                self.table.setItem(r, c, _cell(text))
        self._apply_filter(self.filter.text())
        self.status.setText(f"Служб: {len(self._rows)}")

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for r, s in enumerate(self._rows):
            match = (not needle) or needle in s["unit"].lower() or needle in s["desc"].lower()
            self.table.setRowHidden(r, not match)

    def _action(self, action: str) -> None:
        row = self.table.currentRow()
        if row < 0 or self._busy:
            self.status.setText("Выбери службу в списке")
            return
        unit = self.table.item(row, 0).text()
        self._busy = True
        self.status.setText(f"{action}: {unit}…")

        def job():
            return st.service_action(unit, action)

        self._worker = Worker(job)
        self._worker.done.connect(self._action_done)
        self._worker.start()

    def _action_done(self, result) -> None:
        self._busy = False
        if result:
            ok, msg = result
            self.status.setText(("Готово: " if ok else "Ошибка: ") + msg)
        self.refresh()


# =========================================================================== #
class PackagesPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._busy = False
        self._rows: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(_title("Пакеты"))
        self._pkg_desc = dim("Поиск, установка и удаление пакетов. "
                             "Установка/удаление могут запросить пароль.")
        root.addWidget(self._pkg_desc)

        bar = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText("Что искать? например: neovim")
        self.query.returnPressed.connect(self.search)
        bar.addWidget(self.query, 1)
        self.btn_search = QPushButton("Найти")
        self.btn_search.clicked.connect(self.search)
        bar.addWidget(self.btn_search)
        root.addLayout(bar)

        self.table = table(["Пакет", "Версия", "Репозиторий", "Установлен", "Описание"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        root.addWidget(self.table, 2)

        act = QHBoxLayout()
        self.btn_install = QPushButton("Установить")
        self.btn_install.setObjectName("Accent")
        self.btn_install.clicked.connect(self._install)
        self.btn_remove = QPushButton("Удалить")
        self.btn_remove.setObjectName("Danger")
        self.btn_remove.clicked.connect(self._remove)
        act.addWidget(self.btn_install)
        act.addWidget(self.btn_remove)
        act.addStretch(1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        act.addWidget(self.status)
        root.addLayout(act)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Здесь появится вывод менеджера пакетов…")
        self.log.setMaximumHeight(150)
        root.addWidget(self.log)

        mgr = st.package_manager()
        if mgr:
            self._pkg_desc.setText(
                f"Поиск, установка и удаление пакетов ({mgr}). "
                "Установка и удаление могут запросить пароль администратора.")

    def search(self) -> None:
        q = self.query.text().strip()
        if not q or self._busy:
            return
        self._busy = True
        self.status.setText("Поиск…")
        self.btn_search.setEnabled(False)

        def job():
            return st.pacman_search(q)

        self._worker = Worker(job)
        self._worker.done.connect(self._search_done)
        self._worker.start()

    def _search_done(self, rows) -> None:
        self._busy = False
        self.btn_search.setEnabled(True)
        self._rows = rows or []
        self.table.setRowCount(len(self._rows))
        for r, p in enumerate(self._rows):
            for c, text in enumerate([p["name"], p["version"], p["repo"],
                                      "да" if p["installed"] else "—", p["desc"]]):
                self.table.setItem(r, c, _cell(text))
        self.status.setText(f"Найдено: {len(self._rows)}")

    def _selected_names(self) -> list[str]:
        rows = {i.row() for i in self.table.selectedItems()}
        names = []
        for r in sorted(rows):
            item = self.table.item(r, 0)
            if item:
                names.append(item.text())
        return names

    def _install(self) -> None:
        names = self._selected_names()
        if not names or self._busy:
            self.status.setText("Выбери пакет(ы) в таблице")
            return
        self._busy = True
        self.status.setText("Установка… (может появиться запрос пароля)")
        self.log.setPlainText("Установка: " + " ".join(names))

        def job():
            return st.pacman_install(names)

        self._worker = Worker(job)
        self._worker.done.connect(self._action_done)
        self._worker.start()

    def _remove(self) -> None:
        names = self._selected_names()
        if not names or self._busy:
            self.status.setText("Выбери пакет(ы) в таблице")
            return
        self._busy = True
        self.status.setText("Удаление… (может появиться запрос пароля)")
        self.log.setPlainText("Удаление: " + " ".join(names))

        def job():
            return st.pacman_remove(names)

        self._worker = Worker(job)
        self._worker.done.connect(self._action_done)
        self._worker.start()

    def _action_done(self, result) -> None:
        self._busy = False
        if result:
            ok, output = result
            self.log.setPlainText(self.log.toPlainText() + "\n\n" + (output or ""))
            self.status.setText("Готово" if ok else "Ошибка (см. вывод)")
        self.search()


# =========================================================================== #
class NetworkPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._busy = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(_title("Сеть"))
        root.addWidget(dim("Интерфейсы, маршрут, DNS и проверка соединения"))

        bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_ping = QPushButton("Проверить пинг (1.1.1.1)")
        self.btn_ping.clicked.connect(self.ping)
        self.btn_ip = QPushButton("Узнать внешний IP")
        self.btn_ip.clicked.connect(self.external_ip)
        bar.addWidget(self.btn_refresh)
        bar.addWidget(self.btn_ping)
        bar.addWidget(self.btn_ip)
        bar.addStretch(1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        bar.addWidget(self.status)
        root.addLayout(bar)

        self.table = table(["Интерфейс", "Состояние", "Адреса", "MAC"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        root.addWidget(self.table, 1)

        info = card()
        il = QVBoxLayout(info)
        il.setContentsMargins(18, 16, 18, 16)
        t = QLabel("Подробности")
        t.setObjectName("CardTitle")
        il.addWidget(t)
        self.details = QLabel("—")
        self.details.setObjectName("CardSub")
        self.details.setTextFormat(Qt.RichText)
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.details.setWordWrap(True)
        il.addWidget(self.details)
        root.addWidget(info)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self) -> None:
        info = st.network_info()
        ifaces = info["interfaces"]
        self.table.setRowCount(len(ifaces))
        for r, i in enumerate(ifaces):
            for c, text in enumerate([i["name"], i["state"],
                                      ", ".join(i["addrs"]) or "—", i["mac"]]):
                self.table.setItem(r, c, _cell(text))
        dns = ", ".join(info["dns"]) or "—"
        route = info["route"] or "—"
        self.details.setText(
            f"<b>Хост:</b> {info['hostname']}<br>"
            f"<b>Маршрут по умолчанию:</b> {route}<br>"
            f"<b>DNS:</b> {dns}")

    def _run(self, job, on_done) -> None:
        if self._busy:
            return
        self._busy = True
        self._worker = Worker(job)
        self._worker.done.connect(on_done)
        self._worker.start()

    def ping(self) -> None:
        self.status.setText("Пингую 1.1.1.1…")
        self._run(lambda: st.ping_test("1.1.1.1", 4), self._ping_done)

    def _ping_done(self, result) -> None:
        self._busy = False
        if not result:
            self.status.setText("Не удалось выполнить ping")
            return
        if result["ok"]:
            self.status.setText("Есть ответ: " + (result["avg"] or "ок"))
        else:
            self.status.setText("Нет ответа: " + (result["loss"] or "потери пакетов"))

    def external_ip(self) -> None:
        self.status.setText("Определяю внешний IP…")
        self._run(st.public_ip, self._ip_done)

    def _ip_done(self, ip) -> None:
        self._busy = False
        self.status.setText(f"Внешний IP: {ip}" if ip else "Не удалось определить IP")


# =========================================================================== #
class SensorsPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._busy = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(_title("Датчики и нагрузка"))
        root.addWidget(dim("Температуры, вентиляторы, память и средняя загрузка"))

        bar = QHBoxLayout()
        self.auto = QCheckBox("Автообновление")
        self.auto.setChecked(True)
        self.auto.toggled.connect(self._toggle_auto)
        bar.addWidget(self.auto)
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.refresh)
        bar.addWidget(self.btn_refresh)
        bar.addStretch(1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        bar.addWidget(self.status)
        root.addLayout(bar)

        self.summary = card()
        sl = QHBoxLayout(self.summary)
        sl.setContentsMargins(18, 16, 18, 16)
        self.lbl_mem = QLabel("—")
        self.lbl_load = QLabel("—")
        self.lbl_temp = QLabel("—")
        for w in (self.lbl_mem, self.lbl_load, self.lbl_temp):
            w.setObjectName("CardTitle")
            sl.addWidget(w)
        sl.addStretch(1)
        root.addWidget(self.summary)

        self.table = table(["Датчик", "Значение"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        root.addWidget(self.table, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._auto_tick)
        self._start_timer()

    def _start_timer(self) -> None:
        self.timer.start(max(1, self.settings.get_int("tools/refresh_sec")) * 1000)

    def _toggle_auto(self, on: bool) -> None:
        if on:
            self._start_timer()
        else:
            self.timer.stop()

    def _auto_tick(self) -> None:
        if self.isVisible() and self.window().isActiveWindow() and not self._busy:
            self.refresh()

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True

        def job():
            temps, fans = st.sensors_info()
            total, used = st.memory_info()
            return temps, fans, total, used, st.load_avg()

        self._worker = Worker(job)
        self._worker.done.connect(self._done)
        self._worker.start()

    def _done(self, result) -> None:
        self._busy = False
        if not result:
            return
        temps, fans, total, used, load = result
        self.lbl_mem.setText(f"Память: {used:.1f} / {total:.1f} ГБ")
        self.lbl_load.setText(f"Загрузка: {load[0]:.2f} {load[1]:.2f} {load[2]:.2f}")
        if temps:
            self.lbl_temp.setText(f"Макс. темп: {max(t for _, t in temps):.0f} °C")
        else:
            self.lbl_temp.setText("Темп: —")
        rows = [(name, f"{value:.0f} °C") for name, value in temps]
        rows += [(name, f"{value:.0f} об/мин") for name, value in fans]
        self.table.setRowCount(len(rows))
        for r, (name, value) in enumerate(rows):
            self.table.setItem(r, 0, _cell(name))
            self.table.setItem(r, 1, _cell(value, True))
        self.status.setText(f"Датчиков: {len(rows)}")


# =========================================================================== #
class StartupPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._rows: list[dict] = []
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)
        root.addWidget(_title("Автозапуск"))
        root.addWidget(dim("Приложения, стартующие с системой "
                           "(XDG autostart — Linux, объекты входа — macOS, "
                           "реестр и папка «Автозагрузка» — Windows). "
                           "Галочка = включено"))

        bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.refresh)
        bar.addWidget(self.btn_refresh)
        bar.addStretch(1)
        self.status = QLabel("")
        self.status.setObjectName("Dim")
        bar.addWidget(self.status)
        root.addLayout(bar)

        self.table = table(["Вкл", "Название", "Команда", "Источник"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.itemChanged.connect(self._item_changed)
        root.addWidget(self.table, 1)

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self) -> None:
        self._loading = True
        self._rows = st.list_startup()
        self.table.setRowCount(len(self._rows))
        for r, entry in enumerate(self._rows):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk.setCheckState(Qt.Checked if entry["enabled"] else Qt.Unchecked)
            self.table.setItem(r, 0, chk)
            self.table.setItem(r, 1, _cell(entry["name"]))
            self.table.setItem(r, 2, _cell(entry["exec"]))
            self.table.setItem(r, 3, _cell(entry["source"]))
        self._loading = False
        self.status.setText(f"Записей: {len(self._rows)}")

    def _item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading or item.column() != 0:
            return
        row = item.row()
        if row >= len(self._rows):
            return
        entry = self._rows[row]
        enabled = item.checkState() == Qt.Checked
        ok = st.set_startup_enabled(entry, enabled)
        entry["enabled"] = enabled
        self.status.setText(
            f"{entry['name']}: {'включено' if enabled else 'выключено'}"
            + ("" if ok else " (ошибка)"))
