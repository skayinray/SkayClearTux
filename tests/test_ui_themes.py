"""UI-тесты тем оформления — ``skaycleartux.themes``.

Проверяем цветовые преобразования, полноту палитр и то, что генератор QSS
работает для всех тем (в том числе при быстром переключении подряд).
"""
from __future__ import annotations

import re

import pytest

from skaycleartux import themes

REQUIRED_KEYS = {
    "bg", "sidebar", "card", "card2", "border", "text", "dim", "accent",
    "accent_text", "hover", "danger", "success", "board_light", "board_dark",
}


def test_themes_not_empty():
    assert themes.THEMES
    assert themes.DEFAULT_THEME in themes.THEMES


@pytest.mark.parametrize("name", list(themes.THEMES))
def test_each_theme_has_all_keys(name):
    colors = themes.THEMES[name]
    assert REQUIRED_KEYS <= set(colors)
    for key, value in colors.items():
        assert re.fullmatch(r"#[0-9a-fA-F]{6}", value), f"{name}.{key}={value}"


# --------------------------------------------------------------------------- #
#  Цветовые утилиты
# --------------------------------------------------------------------------- #
def test_clamp():
    assert themes._clamp(-5) == 0
    assert themes._clamp(300) == 255
    assert themes._clamp(127.6) == 128


def test_rgb():
    assert themes._rgb("#ff8000") == (255, 128, 0)
    assert themes._rgb("000000") == (0, 0, 0)


def test_shade_lighter_and_darker():
    assert themes.shade("#808080", 1.5) > "#808080"
    assert themes.shade("#808080", 0.5) < "#808080"
    # крайние значения не выходят за диапазон
    assert themes.shade("#ffffff", 2.0) == "#ffffff"
    assert themes.shade("#000000", 0.0) == "#000000"


def test_mix_midpoint():
    assert themes.mix("#000000", "#ffffff", 0.5) == "#808080"
    assert themes.mix("#000000", "#ffffff", 0.0) == "#000000"
    assert themes.mix("#000000", "#ffffff", 1.0) == "#ffffff"


# --------------------------------------------------------------------------- #
#  Генерация QSS
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", list(themes.THEMES))
def test_build_qss_contains_theme_colors(name):
    colors = themes.THEMES[name]
    qss = themes.build_qss(colors)
    assert colors["bg"] in qss
    assert colors["accent"] in qss
    assert "#Root" in qss
    assert "#PaletteList" in qss
    # фигурные скобки в QSS сбалансированы
    assert qss.count("{") == qss.count("}")


def test_rapid_theme_switching_does_not_break():
    # быстрое переключение всех тем подряд не должно падать
    for _ in range(3):
        for name in themes.THEMES:
            qss = themes.build_qss(themes.THEMES[name])
            assert qss.strip()
