"""Точка входа SkayClearTux."""
from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import __app_name__, __version__
from .logging_setup import setup_logging
from .main_window import MainWindow


def main() -> int:
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(f"{__app_name__} {__version__}")
    app.setOrganizationName(__app_name__)
    app.setDesktopFileName("skaycleartux")

    from .resources import asset
    icon = asset("tux.png")
    app.setWindowIcon(QIcon(icon))

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
