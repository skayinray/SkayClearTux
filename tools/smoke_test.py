"""Дымовой тест SkayClearTux (запускается в CI и локально).

Поднимает интерфейс в offscreen-режиме, обходит все страницы, проверяет, что
бэкенд текущей ОС отвечает, и ищет символы, которые Qt рисует пустыми
квадратами (эмодзи и редкие стрелки/геометрические знаки).

Запуск:

    QT_QPA_PLATFORM=offscreen python tools/smoke_test.py
"""
from __future__ import annotations

import os
import sys, os; os.environ['QT_QPA_PLATFORM'] = 'offscreen'

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import (QApplication, QTableWidget)

from skaycleartux import cleaner  # noqa: E402
from skaycleartux import sys, os; os.environ['QT_QPA_PLATFORM'] = 'offscreen'tem_tools as st  # noqa: E402
from skaycleartux.backends import common  # noqa: E402
from skaycleartux.main_window import NAV, MainWindow  # noqa: E402
from skaycleartux.palette import CommandPalette  # noqa: E402

# символы, которых нет в стандартных шрифтах (DejaVu/Noto/Inter)
BAD = set("→←↑↓≈≤≥✓✔●○▾▸▼▶⏵⏴⚫⚪⬤◆◇★☆⯈")


def is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return (0x1F000 <= cp <= 0x1FAFF) or (0x2600 <= cp <= 0x27BF) or cp == 0xFE0F


def bad_glyphs(text: str) -> list[str]:
    return [f"{ch!r}(U+{ord(ch):04X})" for ch in text
            if ch in BAD or is_emoji(ch)]


def iter_widgets(root):
    stack = [root]
    while stack:
        widget = stack.pop()
        yield widget
        stack.extend(c for c in widget.children() if hasattr(c, "children"))


def widget_texts(widget) -> list[str]:
    texts: list[str] = []
    for attr in ("text", "placeholderText", "windowTitle", "toolTip"):
        fn = getattr(widget, attr, None)
        if callable(fn):
            try:
                value = fn()
            except Exception:  # noqa: BLE001
                continue
            if isinstance(value, str) and value:
                texts.append(value)
    if isinstance(widget, QTableWidget):
        for col in range(widget.columnCount()):
            header = widget.horizontalHeaderItem(col)
            if header and header.text():
                texts.append(header.text())
    return texts


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.resize(1280, 820)
    win.show()
    app.processEvents()

    problems: list[str] = []
    expected = sum(len(items) for _section, items in NAV)
    print(f"Платформа: {common.FAMILY} ({common.os_pretty_name()})")
    print(f"Страниц: {win.stack.count()} / ожидалось {expected}")
    if win.stack.count() != expected:
        problems.append("число страниц не совпадает с NAV")

    for key, index in win.key_index.items():
        win.stack.setCurrentIndex(index)
        app.processEvents()
        page = win.stack.widget(index)
        for widget in iter_widgets(page):
            for text in widget_texts(widget):
                found = bad_glyphs(text)
                if found:
                    problems.append(
                        f"[{key}] {type(widget).__name__}: {sorted(set(found))} :: {text[:60]}")

    # бэкенд должен отвечать без исключений
    for name, fn in (
        ("processes", st.list_processes),
        ("services", st.list_services),
        ("memory", st.memory_info),
        ("cpu", st.cpu_percent),
        ("disk", st.disk_usage),
        ("ports", st.listening_ports),
        ("mounts", st.mounts),
        ("hardware", st.hardware_sections),
        ("startup", st.list_startup),
    ):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            problems.append(f"бэкенд {name}: {exc}")

    # палитра команд
    palette = CommandPalette(win._page_list(), win)
    palette._refresh("очис")
    print(f"Палитра команд: {palette.list.count()} совпадений по запросу «очис»")

    print(f"Категорий очистки: {len(cleaner.CATEGORIES)}")
    if common.FAMILY == "linux":
        print(f"Менеджер пакетов: {st.package_manager() or 'не определён'}")

    if problems:
        print("\n=== ПРОБЛЕМЫ ===")
        for problem in problems:
            print(" ", problem)
        return 1

    print("\nOK: проблем не найдено.")
    return 0


if __name__ == "__main__":
    # os._exit обходит падение Qt при завершении в offscreen-режиме,
    # из-за которого процесс мог завершаться сигналом SIGABRT.
    _code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_code)
