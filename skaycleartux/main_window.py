"""Главное окно SkayClearTux: разделы, анимированные переходы, применение настроек."""
from __future__ import annotations

import os
import time
from pathlib import Path

from PySide6.QtCore import (QEasingCurve, QPropertyAnimation, Qt, QTimer,
                            Signal)
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame,
                               QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QMainWindow, QMenu, QMessageBox, QPushButton,
                               QScrollArea, QStackedWidget, QSystemTrayIcon,
                               QVBoxLayout, QWidget)

from . import themes as themes_mod
from . import updater
from . import __version__
from .backends import common as platform_common
from .chess_widget import ChessPage
from .discord_rpc import DiscordPresence
from .extra_pages import (BackupPage, BootPage, DiagnosticsPage, DisksPage,
                          FirewallPage, HardwarePage, HashPage, HelpPage,
                          JournalPage, LargeFilesPage, ModulesPage, MonitorPage,
                          NotesPage, PasswordPage, PkgFilesPage, PortsPage,
                          TextToolsPage, TimersPage, TrashPage, TweaksPage,
                          UpdatesPage)
from .helptext import help_for
from .pages import (AboutPage, CleanerPage, DashboardPage, DiskPage,
                    ThemesPage, Worker)
from .palette import CommandPalette
from .resources import asset
from .settings import CREATOR, Settings
from .settings_page import SettingsPage
from .tools_pages import (NetworkPage, PackagesPage, ProcessesPage,
                          SensorsPage, ServicesPage, StartupPage)

NAV: list[tuple[str, list[tuple[str, str]]]] = [
    ("Обзор", [("Главная", "dash"), ("Монитор", "monitor"),
               ("Датчики", "sensors"), ("Загрузка", "boot")]),
    ("Очистка", [("Очистка", "cleaner"), ("Анализ диска", "disk"),
                 ("Большие файлы", "bigfiles"), ("Корзина", "trash")]),
    ("Инструменты", [("Процессы", "procs"), ("Службы", "services"),
                     ("Таймеры", "timers"), ("Пакеты", "packages"),
                     ("Файлы пакетов", "pkgfiles"), ("Обновления", "updates"),
                     ("Сеть", "network"), ("Порты", "ports"),
                     ("Автозапуск", "startup")]),
    ("Система", [("Железо", "hardware"), ("Диски", "disks"),
                 ("Модули ядра", "modules"), ("Журнал", "journal"),
                 ("Файрвол", "firewall"), ("Диагностика", "diagnostics"),
                 ("Твики", "tweaks")]),
    ("Утилиты", [("Заметки", "notes"), ("Хэши", "hashes"),
                 ("Текст", "texttools"), ("Бэкап", "backup"),
                 ("Пароли", "passwords")]),
    ("Развлечения", [("Шахматы", "chess")]),
    ("Настройка", [("Темы", "themes"), ("Настройки", "settings"),
                   ("Справка", "help"), ("О программе", "about")]),
]


class FadeStack(QStackedWidget):
    """Стек страниц с плавным кроссфейдом.

    Снимок старой страницы накладывается поверх новой и плавно тает — это
    дешевле и ровнее, чем анимировать прозрачность тяжёлых виджетов.
    """

    page_changed = Signal(int)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._anim_out: QPropertyAnimation | None = None
        self._overlay = QLabel(self)
        self._overlay.setObjectName("FadeOverlay")
        self._overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._overlay.hide()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._overlay.setGeometry(0, 0, self.width(), self.height())

    def _snapshot(self, widget: QWidget) -> QPixmap | None:
        if widget is None or widget.width() <= 0 or widget.height() <= 0:
            return None
        pix = widget.grab()
        return None if pix.isNull() else pix

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        if index == self.currentIndex() or not self.settings.get_bool("ui/animations"):
            self._overlay.hide()
            super().setCurrentIndex(index)
            self.page_changed.emit(index)
            return

        duration = max(120, self.settings.get_int("ui/anim_ms"))
        pix = self._snapshot(self.currentWidget())
        super().setCurrentIndex(index)
        self.page_changed.emit(index)
        if pix is None:
            return

        self._overlay.setPixmap(pix)
        self._overlay.setGeometry(0, 0, self.width(), self.height())
        self._overlay.show()
        self._overlay.raise_()
        eff = QGraphicsOpacityEffect(self._overlay)
        self._overlay.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(self._overlay.hide)
        anim.start()
        self._anim_out = anim


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.theme_name = self.settings.get("theme")
        if self.theme_name not in themes_mod.THEMES:
            self.theme_name = themes_mod.DEFAULT_THEME
        self.colors = themes_mod.THEMES[self.theme_name]

        self.setWindowTitle("SkayClearTux")
        self.setMinimumSize(1000, 660)
        self.setWindowIcon(QIcon(asset("tux.png")))

        self.section_items: dict[str, list[QPushButton]] = {}
        self.section_headers: dict[str, QPushButton] = {}

        central = QWidget()
        central.setObjectName("Root")
        self.setCentralWidget(central)
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._sidebar())

        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        self.banner = self._build_banner()
        right_lay.addWidget(self.banner)

        self.stack = FadeStack(self.settings)
        self._create_pages()
        self.key_index: dict[str, int] = {}
        for _section, items in NAV:
            for _label, key in items:
                self.key_index[key] = self.stack.count()
                self.stack.addWidget(self.pages[key])
        self.index_key: dict[int, str] = {v: k for k, v in self.key_index.items()}
        right_lay.addWidget(self.stack, 1)
        lay.addWidget(right, 1)

        self.presence: DiscordPresence | None = None
        self._update_available: dict | None = None
        self._update_busy = False
        self._tray: QSystemTrayIcon | None = None
        self._quitting = False
        self._shortcuts: list[QShortcut] = []

        self.stack.page_changed.connect(self._on_page_changed)

        self._apply_collapsed()
        self._restore_geometry()
        self.apply_theme(self.theme_name)
        self._apply_font_scale()
        self._goto(self.settings.get("ui/start_page"))

        self._setup_shortcuts()
        self._setup_tray()
        self._setup_presence()
        self._maybe_auto_check_updates()

    # -------------------------------------------------------------- страницы
    def _create_pages(self) -> None:
        self.pages: dict[str, QWidget] = {
            "dash": DashboardPage(),
            "monitor": MonitorPage(self.settings, self.colors),
            "sensors": SensorsPage(self.settings),
            "boot": BootPage(self.settings),
            "cleaner": CleanerPage(self.settings),
            "disk": DiskPage(),
            "bigfiles": LargeFilesPage(self.settings),
            "trash": TrashPage(self.settings),
            "procs": ProcessesPage(self.settings),
            "services": ServicesPage(self.settings),
            "timers": TimersPage(self.settings),
            "packages": PackagesPage(self.settings),
            "pkgfiles": PkgFilesPage(self.settings),
            "updates": UpdatesPage(self.settings),
            "network": NetworkPage(self.settings),
            "ports": PortsPage(self.settings),
            "startup": StartupPage(self.settings),
            "hardware": HardwarePage(self.settings),
            "disks": DisksPage(self.settings),
            "modules": ModulesPage(self.settings),
            "journal": JournalPage(self.settings),
            "firewall": FirewallPage(self.settings),
            "diagnostics": DiagnosticsPage(self.settings),
            "tweaks": TweaksPage(self.settings),
            "notes": NotesPage(self.settings),
            "hashes": HashPage(self.settings),
            "texttools": TextToolsPage(self.settings),
            "backup": BackupPage(self.settings),
            "passwords": PasswordPage(self.settings),
            "chess": ChessPage(self.colors, self.settings),
            "themes": ThemesPage(self.apply_theme, self.theme_name),
            "settings": SettingsPage(self.settings, self.apply_theme),
            "help": HelpPage(),
            "about": AboutPage(),
        }
        self.pages["settings"].changed.connect(self._on_settings_changed)
        self.pages["settings"].check_updates.connect(
            lambda: self.check_updates(silent=False))

    # -------------------------------------------------------------- сайдбар
    def _sidebar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("Sidebar")
        bar.setFixedWidth(244)
        outer = QVBoxLayout(bar)
        outer.setContentsMargins(14, 18, 14, 14)
        outer.setSpacing(10)

        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap(asset("tux.png")).scaled(
            44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        brand.addWidget(logo)
        txt = QVBoxLayout()
        txt.setSpacing(0)
        t = QLabel("SkayClearTux")
        t.setObjectName("BrandTitle")
        s = QLabel(f"v{__version__} · {platform_common.os_short_name()}")
        s.setObjectName("BrandSub")
        txt.addWidget(t)
        txt.addWidget(s)
        brand.addLayout(txt)
        brand.addStretch(1)
        outer.addLayout(brand)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        col = QVBoxLayout(holder)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(3)

        self.nav_buttons: list[QPushButton] = []
        group = QButtonGroup(self)
        group.setExclusive(True)
        self._nav_group = group
        index = 0
        show_tips = self.settings.get_bool("ui/show_tips")
        for section, items in NAV:
            header = QPushButton(section.upper())
            header.setObjectName("NavSection")
            header.setCursor(Qt.PointingHandCursor)
            header.setFlat(True)
            header.clicked.connect(
                lambda _=False, name=section: self._toggle_section(name))
            col.addWidget(header)
            self.section_headers[section] = header
            self.section_items[section] = []

            for label, key in items:
                b = QPushButton(label)
                b.setObjectName("Nav")
                b.setCheckable(True)
                b.setCursor(Qt.PointingHandCursor)
                if show_tips:
                    _cat, _name, desc = help_for(key)
                    if desc:
                        b.setToolTip(desc)
                b.clicked.connect(
                    lambda _=False, i=index: self.stack.setCurrentIndex(i))
                group.addButton(b)
                self.nav_buttons.append(b)
                self.section_items[section].append(b)
                col.addWidget(b)
                index += 1
            col.addSpacing(4)
        col.addStretch(1)
        scroll.setWidget(holder)
        outer.addWidget(scroll, 1)

        self.theme_hint = QLabel()
        self.theme_hint.setObjectName("BrandSub")
        self.theme_hint.setWordWrap(True)
        outer.addWidget(self.theme_hint)

        credit = QLabel(f"Создатель: {CREATOR}")
        credit.setObjectName("BrandSub")
        credit.setWordWrap(True)
        credit.setTextInteractionFlags(Qt.TextSelectableByMouse)
        outer.addWidget(credit)
        return bar

    # ------------------------------------------------------- сворачивание
    def _collapsed_set(self) -> set[str]:
        raw = str(self.settings.get("ui/collapsed") or "")
        return {s for s in (x.strip() for x in raw.split(",")) if s}

    def _toggle_section(self, name: str) -> None:
        collapsed = self._collapsed_set()
        if name in collapsed:
            collapsed.discard(name)
        else:
            collapsed.add(name)
        self.settings.set("ui/collapsed", ",".join(sorted(collapsed)))
        self.settings.save()
        self._apply_collapsed()

    def _apply_collapsed(self) -> None:
        collapsed = self._collapsed_set()
        for name, buttons in self.section_items.items():
            is_collapsed = name in collapsed
            for b in buttons:
                b.setVisible(not is_collapsed)
            header = self.section_headers.get(name)
            if header is not None:
                arrow = "+" if is_collapsed else "−"
                header.setText(f"{arrow}  {name.upper()}")
                header.setToolTip("Развернуть раздел" if is_collapsed
                                  else "Свернуть раздел")

    # ---------------------------------------------------------------- навигация
    def _goto(self, key: str) -> None:
        index = self.key_index.get(key, 0)
        self.stack.setCurrentIndex(index)
        if 0 <= index < len(self.nav_buttons):
            self.nav_buttons[index].setChecked(True)

    def _apply_tips(self) -> None:
        show = self.settings.get_bool("ui/show_tips")
        for _section, items in NAV:
            for _label, key in items:
                btn = self.nav_buttons[self.key_index[key]]
                if show:
                    _cat, _name, desc = help_for(key)
                    btn.setToolTip(desc)
                else:
                    btn.setToolTip("")

    # ---------------------------------------------------------- палитра команд
    def _page_list(self) -> list[tuple[str, str]]:
        return [(key, label) for _section, items in NAV for label, key in items]

    def open_palette(self) -> None:
        dlg = CommandPalette(self._page_list(), self)
        dlg.activated.connect(self._goto)
        dlg.action.connect(self._run_action)
        dlg.exec()

    def _run_action(self, name: str) -> None:
        if name == "check_updates":
            self.check_updates(silent=False)
        elif name in ("themes", "settings", "help", "about"):
            self._goto(name)
        elif name == "quit":
            self._quit()

    # ------------------------------------------------------ горячие клавиши
    def _setup_shortcuts(self) -> None:
        for sc in self._shortcuts:
            sc.setEnabled(False)
        self._shortcuts = []
        if not self.settings.get_bool("ui/hotkeys"):
            return

        def add(seq: str, fn) -> None:
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(fn)
            self._shortcuts.append(sc)

        add("Ctrl+K", self.open_palette)
        add("Ctrl+F", self.open_palette)
        add("F1", lambda: self._goto("help"))
        add("Ctrl+Q", self._quit)
        add("Ctrl+,", lambda: self._goto("settings"))
        add("Ctrl+R", self._refresh_current)
        add("Ctrl+H", lambda: self._goto("dash"))
        add("Ctrl+Tab", lambda: self._cycle_page(1))
        add("Ctrl+Shift+Tab", lambda: self._cycle_page(-1))

    def _cycle_page(self, step: int) -> None:
        count = self.stack.count()
        if count == 0:
            return
        index = (self.stack.currentIndex() + step) % count
        self.stack.setCurrentIndex(index)
        if 0 <= index < len(self.nav_buttons):
            self.nav_buttons[index].setChecked(True)

    def _refresh_current(self) -> None:
        page = self.stack.currentWidget()
        for name in ("refresh", "reload", "scan", "_refresh", "reload_data"):
            fn = getattr(page, name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:  # noqa: BLE001 — обновление не должно падать
                    pass
                return

    # --------------------------------------------------------------- трей
    def _setup_tray(self) -> None:
        if self._tray is not None:
            self._tray.hide()
            self._tray = None
        if not self.settings.get_bool("ui/tray"):
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(QIcon(asset("tux.png")), self)
        tray.setToolTip("SkayClearTux")
        menu = QMenu()
        show = QAction("Показать окно", self)
        show.triggered.connect(self._show_from_tray)
        menu.addAction(show)
        menu.addSeparator()
        for key in ("dash", "monitor", "cleaner", "procs", "settings"):
            _cat, name, _desc = help_for(key)
            act = QAction(name, self)
            act.triggered.connect(lambda _=False, k=key: self._goto_from_tray(k))
            menu.addAction(act)
        menu.addSeparator()
        upd = QAction("Проверить обновления", self)
        upd.triggered.connect(lambda: self.check_updates(silent=False))
        menu.addAction(upd)
        quit_act = QAction("Выйти", self)
        quit_act.triggered.connect(self._quit)
        menu.addAction(quit_act)
        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        self._tray = tray

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.isVisible() and not self.isMinimized():
                self.hide()
            else:
                self._show_from_tray()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _goto_from_tray(self, key: str) -> None:
        self._show_from_tray()
        self._goto(key)

    def _quit(self) -> None:
        self._quitting = True
        self.close()
        QApplication.quit()

    # ----------------------------------------------------------- Discord
    def _setup_presence(self) -> None:
        if self.presence is not None:
            self.presence.stop()
            self.presence = None
        if not self.settings.get_bool("discord/enabled"):
            return
        client_id = str(self.settings.get("discord/client_id") or "").strip()
        if not client_id.isdigit():
            return
        self.presence = DiscordPresence(client_id)
        self.presence.start()
        self._on_page_changed(self.stack.currentIndex())

    def _on_page_changed(self, index: int) -> None:
        if self.presence is None:
            return
        key = self.index_key.get(index, "")
        _cat, name, _desc = help_for(key)
        state = f"SkayClearTux v{__version__} · {platform_common.os_short_name()}"
        if self.settings.get_bool("discord/show_page") and name:
            self.presence.update(f"Раздел: {name}", state)
        else:
            self.presence.update("В программе", state)

    # ------------------------------------------------------ обновления
    def _build_banner(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("Banner")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(18, 10, 12, 10)
        lay.setSpacing(12)
        self.banner_label = QLabel("")
        self.banner_label.setObjectName("BannerText")
        self.banner_label.setWordWrap(True)
        lay.addWidget(self.banner_label, 1)
        self.banner_btn = QPushButton("Обновить")
        self.banner_btn.setObjectName("Accent")
        self.banner_btn.clicked.connect(self._do_update)
        lay.addWidget(self.banner_btn)
        later = QPushButton("Позже")
        later.clicked.connect(lambda: bar.setVisible(False))
        lay.addWidget(later)
        bar.setVisible(False)
        return bar

    def _maybe_auto_check_updates(self) -> None:
        url = str(self.settings.get("update/manifest_url") or "").strip()
        if url and self.settings.get_bool("update/auto_check"):
            QTimer.singleShot(2500, lambda: self.check_updates(silent=True))

    def check_updates(self, silent: bool = False) -> None:
        if self._update_busy:
            return
        url = str(self.settings.get("update/manifest_url") or "").strip()
        if not url:
            if not silent:
                QMessageBox.information(
                    self, "Обновления",
                    "Не задан адрес манифеста обновлений.\n"
                    "Настройки → Обновление программы.")
            return

        self._update_busy = True

        def task():
            try:
                return {"ok": True, "data": updater.fetch_manifest(url)}
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "error": str(e)}

        self._update_worker = Worker(task)
        self._update_worker.done.connect(
            lambda res: self._updates_checked(res, silent))
        self._update_worker.start()

    def _updates_checked(self, result, silent: bool) -> None:
        self._update_busy = False
        if not result or not result.get("ok"):
            if not silent:
                error = (result or {}).get("error", "неизвестная ошибка")
                QMessageBox.warning(self, "Обновления",
                                    f"Не удалось проверить обновления:\n{error}")
            return
        data = result["data"]
        self.settings.set("update/last_check", int(time.time()))
        remote = str(data.get("version", ""))
        if updater.is_newer(remote, __version__):
            self._update_available = data
            notes = str(data.get("notes", "")).strip()
            text = f"Доступно обновление SkayClearTux {remote} (у вас {__version__})."
            if notes:
                text += f" {notes}"
            self.banner_label.setText(text)
            self.banner_btn.setEnabled(True)
            self.banner_btn.setText("Обновить")
            self.banner.setVisible(True)
        elif not silent:
            QMessageBox.information(
                self, "Обновления",
                f"У вас последняя версия — {__version__}.")

    def _do_update(self) -> None:
        info = self._update_available
        if not info or self._update_busy:
            return
        url = str(info.get("url") or "").strip()
        if not url:
            QMessageBox.warning(self, "Обновление",
                                "В манифесте не указан адрес файла.")
            return

        target = updater.appimage_path()
        filename = url.split("/")[-1] or "SkayClearTux.AppImage"
        if not target:
            downloads = Path.home() / "Загрузки"
            if not downloads.is_dir():
                downloads = Path.home() / "Downloads"
            target = str(downloads / filename)

        sha = str(info.get("sha256") or "")
        self._update_busy = True
        self.banner_btn.setEnabled(False)
        self.banner_label.setText("Скачиваю обновление…")

        def task():
            dest = updater.temp_download_path(filename)
            updater.download(url, dest, sha)
            return str(dest)

        self._download_worker = Worker(task)
        self._download_worker.done.connect(
            lambda dest: self._update_downloaded(dest, target, bool(updater.appimage_path())))
        self._download_worker.start()

    def _update_downloaded(self, dest, target: str, is_appimage: bool) -> None:
        self._update_busy = False
        if not dest:
            self.banner_label.setText(
                "Не удалось скачать обновление. Проверьте соединение и адрес.")
            self.banner_btn.setEnabled(True)
            return
        if is_appimage:
            try:
                updater.install_appimage(Path(dest), target)
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "Обновление",
                                    f"Не удалось установить обновление:\n{e}")
                self.banner_btn.setEnabled(True)
                return
            QMessageBox.information(
                self, "Обновление",
                "Обновление установлено. Сейчас программа перезапустится.")
            updater.restart(target)
            QApplication.quit()
        else:
            try:
                os.replace(dest, target)
            except OSError:
                pass
            self.banner_label.setText(f"Обновление сохранено: {target}")
            self.banner_btn.setEnabled(False)
            QMessageBox.information(
                self, "Обновление",
                f"Файл обновления сохранён:\n{target}\n\n"
                "Запустите его вручную после закрытия программы.")

    # ---------------------------------------------------------------- темы
    def apply_theme(self, name: str) -> None:
        if name not in themes_mod.THEMES:
            return
        self.theme_name = name
        self.colors = themes_mod.THEMES[name]
        app = QApplication.instance()
        if app:
            app.setStyleSheet(themes_mod.build_qss(self.colors))
        chess = self.pages.get("chess")
        if chess is not None:
            chess.view.light = self.colors["board_light"]
            chess.view.dark = self.colors["board_dark"]
            chess.view.update()
        monitor = self.pages.get("monitor")
        if monitor is not None:
            monitor.apply_theme(self.colors)
        themes_page = self.pages.get("themes")
        if themes_page is not None:
            themes_page.set_current(name)
        settings_page = self.pages.get("settings")
        if settings_page is not None:
            settings_page.sync_theme(name)
        self.theme_hint.setText(f"Тема: {name}")
        self.settings.set("theme", name)

    # ---------------------------------------------------------------- шрифт
    def _apply_font_scale(self) -> None:
        app = QApplication.instance()
        if not app:
            return
        font = app.font()
        base = getattr(self, "_base_point", None)
        if base is None:
            base = font.pointSizeF() if font.pointSizeF() > 0 else 10.0
            self._base_point = base
        scale = max(70, self.settings.get_int("ui/font_scale")) / 100.0
        font.setPointSizeF(base * scale)
        app.setFont(font)

    def _on_settings_changed(self) -> None:
        chess = self.pages.get("chess")
        if chess is not None:
            chess.apply_settings()
        monitor = self.pages.get("monitor")
        if monitor is not None:
            monitor.apply_theme(self.colors)
        settings_page = self.pages.get("settings")
        if settings_page is not None:
            settings_page._sync_elo_label()
        self._apply_tips()
        self._apply_font_scale()
        self._setup_shortcuts()
        self._setup_tray()
        self._setup_presence()

    # ---------------------------------------------------------------- окно
    def _restore_geometry(self) -> None:
        geo = self.settings.get("ui/geometry", b"")
        restored = False
        if self.settings.get_bool("ui/remember_window") and geo:
            restored = self.restoreGeometry(geo)
        if not restored:
            self.resize(1240, 820)

    def closeEvent(self, event) -> None:  # noqa: N802
        if (not self._quitting and self._tray is not None
                and self.settings.get_bool("ui/close_to_tray")):
            event.ignore()
            self.hide()
            if (self.settings.get_bool("ui/tray_notify")
                    and not self.settings.get_bool("ui/tray_hint_shown")):
                self._tray.showMessage(
                    "SkayClearTux",
                    "Программа свёрнута в трей и продолжает работать.",
                    QSystemTrayIcon.Information, 4000)
                self.settings.set("ui/tray_hint_shown", True)
                self.settings.save()
            return
        if self.settings.get_bool("ui/confirm_exit") and not self._quitting:
            ans = QMessageBox.question(
                self, "Выход", "Закрыть SkayClearTux?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ans != QMessageBox.Yes:
                event.ignore()
                return
        if self.settings.get_bool("ui/remember_window"):
            self.settings.set("ui/geometry", self.saveGeometry())
        if self.presence is not None:
            self.presence.stop()
        if self._tray is not None:
            self._tray.hide()
        super().closeEvent(event)
