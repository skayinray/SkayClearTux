"""Страница настроек SkayClearTux."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from . import themes as themes_mod
from . import __version__
from .settings import CREATOR

# порядок ключей страниц для «стартовой страницы»
START_PAGES: list[tuple[str, str]] = [
    ("dash", "Главная"),
    ("monitor", "Монитор"),
    ("sensors", "Датчики"),
    ("boot", "Загрузка"),
    ("cleaner", "Очистка"),
    ("disk", "Анализ диска"),
    ("bigfiles", "Большие файлы"),
    ("trash", "Корзина"),
    ("procs", "Процессы"),
    ("services", "Службы"),
    ("timers", "Таймеры"),
    ("packages", "Пакеты"),
    ("pkgfiles", "Файлы пакетов"),
    ("updates", "Обновления"),
    ("network", "Сеть"),
    ("ports", "Порты"),
    ("startup", "Автозапуск"),
    ("hardware", "Железо"),
    ("disks", "Диски"),
    ("modules", "Модули ядра"),
    ("journal", "Журнал"),
    ("firewall", "Файрвол"),
    ("diagnostics", "Диагностика"),
    ("tweaks", "Твики"),
    ("notes", "Заметки"),
    ("hashes", "Хэши"),
    ("texttools", "Текст"),
    ("backup", "Бэкап"),
    ("passwords", "Пароли"),
    ("chess", "Шахматы"),
    ("themes", "Темы"),
    ("help", "Справка"),
    ("about", "О программе"),
]


def card() -> QFrame:
    f = QFrame()
    f.setObjectName("Card")
    return f


def _dim(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Dim")
    lbl.setWordWrap(True)
    return lbl


def _section(title_text: str) -> QLabel:
    lbl = QLabel(title_text)
    lbl.setObjectName("CardTitle")
    return lbl


class SettingsPage(QWidget):
    changed = Signal()
    check_updates = Signal()

    def __init__(self, settings, on_theme, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.on_theme = on_theme
        self._loading = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(14)
        head = QLabel("Настройки")
        head.setObjectName("H1")
        outer.addWidget(head)
        outer.addWidget(_dim("Всё применяется сразу и запоминается между запусками"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        root = QVBoxLayout(holder)
        root.setContentsMargins(0, 0, 6, 0)
        root.setSpacing(14)

        root.addWidget(self._appearance_card())
        root.addWidget(self._window_card())
        root.addWidget(self._chess_card())
        root.addWidget(self._cleaner_card())
        root.addWidget(self._tools_card())
        root.addWidget(self._discord_card())
        root.addWidget(self._update_card())

        footer = QHBoxLayout()
        self.btn_reset = QPushButton("Сбросить настройки")
        self.btn_reset.clicked.connect(self._reset)
        footer.addWidget(self.btn_reset)
        footer.addStretch(1)
        root.addLayout(footer)

        root.addWidget(self._creator_card())
        root.addStretch(1)
        scroll.setWidget(holder)
        outer.addWidget(scroll, 1)

        self._loading = False

    # ------------------------------------------------------------ секции
    def _appearance_card(self) -> QFrame:
        c = card()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        lay.addWidget(_section("Оформление"))

        row = QHBoxLayout()
        row.addWidget(QLabel("Тема"))
        self.theme_box = QComboBox()
        self.theme_box.addItems(themes_mod.THEMES.keys())
        self.theme_box.setCurrentText(self.settings.get("theme"))
        self.theme_box.currentTextChanged.connect(self._theme_changed)
        row.addWidget(self.theme_box)
        row.addStretch(1)
        lay.addLayout(row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(8)
        grid.addWidget(QLabel("Масштаб шрифта, %"), 0, 0)
        self.spin_font = QSpinBox()
        self.spin_font.setRange(70, 160)
        self.spin_font.setSingleStep(5)
        self.spin_font.setSuffix(" %")
        self.spin_font.setValue(self.settings.get_int("ui/font_scale"))
        self.spin_font.valueChanged.connect(
            lambda v: self._save("ui/font_scale", v))
        grid.addWidget(self.spin_font, 0, 1)
        grid.setColumnStretch(2, 1)
        lay.addLayout(grid)

        self.chk_anim = QCheckBox("Плавные переходы между страницами")
        self.chk_anim.setChecked(self.settings.get_bool("ui/animations"))
        self.chk_anim.toggled.connect(self._anim_toggled)
        lay.addWidget(self.chk_anim)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Длительность анимации, мс"))
        self.spin_anim = QSpinBox()
        self.spin_anim.setRange(60, 600)
        self.spin_anim.setSingleStep(20)
        self.spin_anim.setValue(self.settings.get_int("ui/anim_ms"))
        self.spin_anim.valueChanged.connect(
            lambda v: self._save("ui/anim_ms", v))
        self.spin_anim.setEnabled(self.chk_anim.isChecked())
        row2.addWidget(self.spin_anim)
        row2.addStretch(1)
        lay.addLayout(row2)
        return c

    def _window_card(self) -> QFrame:
        c = card()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        lay.addWidget(_section("Окно и запуск"))

        row = QHBoxLayout()
        row.addWidget(QLabel("Стартовая страница"))
        self.start_box = QComboBox()
        for key, label in START_PAGES:
            self.start_box.addItem(label, key)
        current = self.settings.get("ui/start_page")
        for i in range(self.start_box.count()):
            if self.start_box.itemData(i) == current:
                self.start_box.setCurrentIndex(i)
                break
        self.start_box.currentIndexChanged.connect(
            lambda _i: self._save("ui/start_page", self.start_box.currentData()))
        row.addWidget(self.start_box)
        row.addStretch(1)
        lay.addLayout(row)

        self.chk_geometry = QCheckBox("Запоминать размер и положение окна")
        self.chk_geometry.setChecked(self.settings.get_bool("ui/remember_window"))
        self.chk_geometry.toggled.connect(
            lambda v: self._save("ui/remember_window", v))
        lay.addWidget(self.chk_geometry)

        self.chk_exit = QCheckBox("Спрашивать подтверждение при выходе")
        self.chk_exit.setChecked(self.settings.get_bool("ui/confirm_exit"))
        self.chk_exit.toggled.connect(
            lambda v: self._save("ui/confirm_exit", v))
        lay.addWidget(self.chk_exit)

        self.chk_tips = QCheckBox("Показывать подсказки при наведении на меню")
        self.chk_tips.setChecked(self.settings.get_bool("ui/show_tips"))
        self.chk_tips.toggled.connect(
            lambda v: self._save("ui/show_tips", v))
        lay.addWidget(self.chk_tips)

        self.chk_tray = QCheckBox("Значок программы в системном трее")
        self.chk_tray.setChecked(self.settings.get_bool("ui/tray"))
        self.chk_tray.toggled.connect(
            lambda v: self._save("ui/tray", v))
        lay.addWidget(self.chk_tray)

        self.chk_close_tray = QCheckBox("Сворачивать в трей при закрытии окна")
        self.chk_close_tray.setChecked(self.settings.get_bool("ui/close_to_tray"))
        self.chk_close_tray.toggled.connect(
            lambda v: self._save("ui/close_to_tray", v))
        lay.addWidget(self.chk_close_tray)

        self.chk_hotkeys = QCheckBox("Горячие клавиши (Ctrl+K — палитра команд)")
        self.chk_hotkeys.setChecked(self.settings.get_bool("ui/hotkeys"))
        self.chk_hotkeys.toggled.connect(
            lambda v: self._save("ui/hotkeys", v))
        lay.addWidget(self.chk_hotkeys)
        return c

    def _chess_card(self) -> QFrame:
        c = card()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        lay.addWidget(_section("Шахматы"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(8)
        grid.addWidget(QLabel("Сложность бота"), 0, 0)
        self.diff_box = QComboBox()
        self.diff_box.addItems(["Новичок", "Легко", "Средне", "Сложно"])
        self.diff_box.setCurrentText(self.settings.get("chess/difficulty"))
        self.diff_box.currentTextChanged.connect(
            lambda t: self._save("chess/difficulty", t))
        grid.addWidget(self.diff_box, 0, 1)
        grid.addWidget(QLabel("Играю за"), 1, 0)
        self.side_box = QComboBox()
        self.side_box.addItems(["Белые", "Чёрные"])
        self.side_box.setCurrentText(self.settings.get("chess/side"))
        self.side_box.currentTextChanged.connect(
            lambda t: self._save("chess/side", t))
        grid.addWidget(self.side_box, 1, 1)
        grid.setColumnStretch(2, 1)
        lay.addLayout(grid)

        self.chk_coords = QCheckBox("Показывать координаты (a–h, 1–8)")
        self.chk_coords.setChecked(self.settings.get_bool("chess/show_coords"))
        self.chk_coords.toggled.connect(
            lambda v: self._save("chess/show_coords", v))
        lay.addWidget(self.chk_coords)

        self.chk_hints = QCheckBox("Показывать возможные ходы выбранной фигуры")
        self.chk_hints.setChecked(self.settings.get_bool("chess/show_hints"))
        self.chk_hints.toggled.connect(
            lambda v: self._save("chess/show_hints", v))
        lay.addWidget(self.chk_hints)

        self.chk_last = QCheckBox("Подсвечивать последний ход")
        self.chk_last.setChecked(self.settings.get_bool("chess/highlight_last"))
        self.chk_last.toggled.connect(
            lambda v: self._save("chess/highlight_last", v))
        lay.addWidget(self.chk_last)

        self.chk_anim_move = QCheckBox("Анимировать перемещение фигур")
        self.chk_anim_move.setChecked(self.settings.get_bool("chess/animate"))
        self.chk_anim_move.toggled.connect(
            lambda v: self._save("chess/animate", v))
        lay.addWidget(self.chk_anim_move)

        self.chk_auto_queen = QCheckBox("Автоматически превращать пешку в ферзя")
        self.chk_auto_queen.setChecked(self.settings.get_bool("chess/auto_queen"))
        self.chk_auto_queen.toggled.connect(
            lambda v: self._save("chess/auto_queen", v))
        lay.addWidget(self.chk_auto_queen)

        self.chk_move_list = QCheckBox("Показывать список ходов")
        self.chk_move_list.setChecked(
            self.settings.get_bool("chess/show_move_list"))
        self.chk_move_list.toggled.connect(
            lambda v: self._save("chess/show_move_list", v))
        lay.addWidget(self.chk_move_list)

        elo_row = QHBoxLayout()
        self.elo_label = QLabel("")
        self.elo_label.setObjectName("CardSub")
        elo_row.addWidget(self.elo_label)
        elo_row.addStretch(1)
        self.btn_elo_reset = QPushButton("Сбросить рейтинг Эло")
        self.btn_elo_reset.clicked.connect(self._reset_elo)
        elo_row.addWidget(self.btn_elo_reset)
        lay.addLayout(elo_row)
        self._sync_elo_label()
        return c

    def _sync_elo_label(self) -> None:
        elo = self.settings.get_int("chess/elo")
        best = self.settings.get_int("chess/best_elo")
        games = self.settings.get_int("chess/games")
        wins = self.settings.get_int("chess/wins")
        draws = self.settings.get_int("chess/draws")
        losses = self.settings.get_int("chess/losses")
        self.elo_label.setText(
            f"Эло: {elo} (лучший {best}) · партий {games}: "
            f"{wins}П / {draws}Н / {losses}Пр")

    def _reset_elo(self) -> None:
        self.settings.set("chess/elo", 1200)
        self.settings.set("chess/best_elo", 1200)
        self.settings.set("chess/games", 0)
        self.settings.set("chess/wins", 0)
        self.settings.set("chess/losses", 0)
        self.settings.set("chess/draws", 0)
        self.settings.save()
        self._sync_elo_label()
        self.changed.emit()

    def _cleaner_card(self) -> QFrame:
        c = card()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        lay.addWidget(_section("Очистка"))

        self.chk_confirm = QCheckBox("Спрашивать подтверждение перед очисткой")
        self.chk_confirm.setChecked(self.settings.get_bool("cleaner/confirm"))
        self.chk_confirm.toggled.connect(
            lambda v: self._save("cleaner/confirm", v))
        lay.addWidget(self.chk_confirm)

        self.chk_safe = QCheckBox("По умолчанию выбирать только безопасные категории")
        self.chk_safe.setChecked(self.settings.get_bool("cleaner/select_safe"))
        self.chk_safe.toggled.connect(
            lambda v: self._save("cleaner/select_safe", v))
        lay.addWidget(self.chk_safe)
        return c

    def _tools_card(self) -> QFrame:
        c = card()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        lay.addWidget(_section("Инструменты"))

        row = QHBoxLayout()
        row.addWidget(QLabel("Интервал автообновления, сек"))
        self.spin_refresh = QSpinBox()
        self.spin_refresh.setRange(1, 60)
        self.spin_refresh.setValue(self.settings.get_int("tools/refresh_sec"))
        self.spin_refresh.valueChanged.connect(
            lambda v: self._save("tools/refresh_sec", v))
        row.addWidget(self.spin_refresh)
        row.addStretch(1)
        lay.addLayout(row)

        self.chk_kernel = QCheckBox("Скрывать системные потоки ядра в списке процессов")
        self.chk_kernel.setChecked(self.settings.get_bool("tools/hide_kernel"))
        self.chk_kernel.toggled.connect(
            lambda v: self._save("tools/hide_kernel", v))
        lay.addWidget(self.chk_kernel)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Строк журнала по умолчанию"))
        self.spin_journal = QSpinBox()
        self.spin_journal.setRange(50, 5000)
        self.spin_journal.setSingleStep(50)
        self.spin_journal.setValue(self.settings.get_int("journal/lines"))
        self.spin_journal.valueChanged.connect(
            lambda v: self._save("journal/lines", v))
        row2.addWidget(self.spin_journal)
        row2.addStretch(1)
        lay.addLayout(row2)
        return c

    def _discord_card(self) -> QFrame:
        c = card()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        lay.addWidget(_section("Discord (активность)"))

        self.chk_discord = QCheckBox("Показывать, что я в SkayClearTux")
        self.chk_discord.setChecked(self.settings.get_bool("discord/enabled"))
        self.chk_discord.toggled.connect(
            lambda v: self._save("discord/enabled", v))
        lay.addWidget(self.chk_discord)

        self.chk_discord_page = QCheckBox("Показывать текущий раздел программы")
        self.chk_discord_page.setChecked(
            self.settings.get_bool("discord/show_page"))
        self.chk_discord_page.toggled.connect(
            lambda v: self._save("discord/show_page", v))
        lay.addWidget(self.chk_discord_page)

        row = QHBoxLayout()
        row.addWidget(QLabel("Application ID"))
        self.edit_discord_id = QLineEdit(str(self.settings.get("discord/client_id") or ""))
        self.edit_discord_id.setPlaceholderText("числовой ID приложения Discord")
        self.edit_discord_id.editingFinished.connect(self._save_discord_id)
        row.addWidget(self.edit_discord_id, 1)
        lay.addLayout(row)

        hint = QLabel(
            "Статус «играет в SkayClearTux» виден, пока программа открыта. "
            "Укажите Application ID своего приложения с "
            "discord.com/developers/applications — после этого активность "
            "появится в Discord автоматически (включая Windows, macOS и Linux).")
        hint.setObjectName("CardSub")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        return c

    def _update_card(self) -> QFrame:
        c = card()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        lay.addWidget(_section("Обновление программы"))

        self.lbl_version = QLabel(f"Установленная версия: {__version__}")
        self.lbl_version.setObjectName("CardSub")
        lay.addWidget(self.lbl_version)

        row = QHBoxLayout()
        row.addWidget(QLabel("Адрес манифеста"))
        self.edit_manifest = QLineEdit(str(self.settings.get("update/manifest_url") or ""))
        self.edit_manifest.setPlaceholderText("из коробки: официальный релиз GitHub")
        self.edit_manifest.editingFinished.connect(
            lambda: self._save("update/manifest_url", self.edit_manifest.text().strip()))
        row.addWidget(self.edit_manifest, 1)
        lay.addLayout(row)

        row2 = QHBoxLayout()
        self.chk_autoupdate = QCheckBox("Проверять обновления при запуске")
        self.chk_autoupdate.setChecked(self.settings.get_bool("update/auto_check"))
        self.chk_autoupdate.toggled.connect(
            lambda v: self._save("update/auto_check", v))
        row2.addWidget(self.chk_autoupdate)
        row2.addStretch(1)
        self.btn_check_update = QPushButton("Проверить сейчас")
        self.btn_check_update.setObjectName("Accent")
        self.btn_check_update.clicked.connect(self.check_updates.emit)
        row2.addWidget(self.btn_check_update)
        lay.addLayout(row2)

        hint = QLabel(
            "Обновления работают из коробки — при запуске программа сама проверяет "
            "новые версии на GitHub. Для AppImage обновление скачивается, "
            "проверяется по контрольной сумме и устанавливается автоматически.")
        hint.setObjectName("CardSub")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        return c

    def _save_discord_id(self) -> None:
        self._save("discord/client_id", self.edit_discord_id.text().strip())

    def _creator_card(self) -> QFrame:
        c = card()
        lay = QHBoxLayout(c)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(14)
        info = QVBoxLayout()
        info.setSpacing(2)
        name = QLabel(f"SkayClearTux v{__version__}")
        name.setObjectName("CardTitle")
        author = QLabel(f"Создатель: <b>{CREATOR}</b>")
        author.setTextFormat(Qt.RichText)
        author.setTextInteractionFlags(Qt.TextSelectableByMouse)
        author.setObjectName("CardSub")
        info.addWidget(name)
        info.addWidget(author)
        lay.addLayout(info)
        lay.addStretch(1)
        return c

    # ------------------------------------------------------------ логика
    def _anim_toggled(self, value: bool) -> None:
        self.spin_anim.setEnabled(value)
        self._save("ui/animations", value)

    def _save(self, key: str, value) -> None:
        if self._loading:
            return
        self.settings.set(key, value)
        self.changed.emit()

    def _theme_changed(self, name: str) -> None:
        if self._loading:
            return
        self.on_theme(name)

    def sync_theme(self, name: str) -> None:
        """Обновить комбобокс, если тема сменилась со страницы «Темы»."""
        if self.theme_box.currentText() != name:
            self._loading = True
            self.theme_box.setCurrentText(name)
            self._loading = False

    def _reset(self) -> None:
        self.settings.reset()
        self._loading = True
        self.theme_box.setCurrentText(self.settings.get("theme"))
        self.spin_font.setValue(self.settings.get_int("ui/font_scale"))
        self.chk_anim.setChecked(self.settings.get_bool("ui/animations"))
        self.spin_anim.setValue(self.settings.get_int("ui/anim_ms"))
        self.spin_anim.setEnabled(self.chk_anim.isChecked())
        current = self.settings.get("ui/start_page")
        for i in range(self.start_box.count()):
            if self.start_box.itemData(i) == current:
                self.start_box.setCurrentIndex(i)
                break
        self.chk_geometry.setChecked(self.settings.get_bool("ui/remember_window"))
        self.chk_exit.setChecked(self.settings.get_bool("ui/confirm_exit"))
        self.diff_box.setCurrentText(self.settings.get("chess/difficulty"))
        self.side_box.setCurrentText(self.settings.get("chess/side"))
        self.chk_coords.setChecked(self.settings.get_bool("chess/show_coords"))
        self.chk_hints.setChecked(self.settings.get_bool("chess/show_hints"))
        self.chk_last.setChecked(self.settings.get_bool("chess/highlight_last"))
        self.chk_anim_move.setChecked(self.settings.get_bool("chess/animate"))
        self.chk_auto_queen.setChecked(self.settings.get_bool("chess/auto_queen"))
        self.chk_move_list.setChecked(
            self.settings.get_bool("chess/show_move_list"))
        self.chk_confirm.setChecked(self.settings.get_bool("cleaner/confirm"))
        self.chk_safe.setChecked(self.settings.get_bool("cleaner/select_safe"))
        self.spin_refresh.setValue(self.settings.get_int("tools/refresh_sec"))
        self.chk_kernel.setChecked(self.settings.get_bool("tools/hide_kernel"))
        self.chk_tips.setChecked(self.settings.get_bool("ui/show_tips"))
        self.chk_tray.setChecked(self.settings.get_bool("ui/tray"))
        self.chk_close_tray.setChecked(self.settings.get_bool("ui/close_to_tray"))
        self.chk_hotkeys.setChecked(self.settings.get_bool("ui/hotkeys"))
        self.spin_journal.setValue(self.settings.get_int("journal/lines"))
        self.chk_discord.setChecked(self.settings.get_bool("discord/enabled"))
        self.chk_discord_page.setChecked(self.settings.get_bool("discord/show_page"))
        self.edit_discord_id.setText(str(self.settings.get("discord/client_id") or ""))
        self.edit_manifest.setText(str(self.settings.get("update/manifest_url") or ""))
        self.chk_autoupdate.setChecked(self.settings.get_bool("update/auto_check"))
        self._sync_elo_label()
        self._loading = False
        self.on_theme(self.settings.get("theme"))
        self.changed.emit()
