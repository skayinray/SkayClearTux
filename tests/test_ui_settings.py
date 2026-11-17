"""UI-тесты обёртки настроек — ``skaycleartux.settings``.

QSettings изолируется фикстурой ``isolated_settings``, поэтому реальные
настройки пользователя не затрагиваются.
"""
from __future__ import annotations

import pytest

from skaycleartux.settings import DEFAULTS, Settings, _as_bool


@pytest.fixture
def settings(isolated_settings):
    s = Settings()
    s.reset()
    return s


@pytest.mark.parametrize("value,expected", [
    (True, True), (False, False), ("true", True), ("1", True),
    ("yes", True), ("on", True), ("да", True), ("no", False),
    ("off", False), ("0", False), ("", False),
])
def test_as_bool(value, expected):
    assert _as_bool(value) is expected


def test_get_uses_default(settings):
    assert settings.get("theme") == DEFAULTS["theme"]
    assert settings.get("ui/anim_ms") == DEFAULTS["ui/anim_ms"]


def test_get_explicit_default(settings):
    assert settings.get("нет/такого", "fallback") == "fallback"


def test_set_get_roundtrip(settings):
    settings.set("theme", "Nord")
    assert settings.get("theme") == "Nord"
    settings.save()
    assert Settings().get("theme") == "Nord"


def test_get_bool(settings):
    settings.set("ui/animations", "false")
    assert settings.get_bool("ui/animations") is False
    settings.set("ui/animations", True)
    assert settings.get_bool("ui/animations") is True


def test_get_int(settings):
    settings.set("ui/anim_ms", "350")
    assert settings.get_int("ui/anim_ms") == 350


def test_get_int_bad_value_falls_back(settings):
    settings.set("ui/font_scale", "не число")
    assert settings.get_int("ui/font_scale") == DEFAULTS["ui/font_scale"]


def test_reset_restores_defaults(settings):
    settings.set("theme", "Роза")
    settings.set("ui/anim_ms", 999)
    settings.reset()
    assert settings.get("theme") == DEFAULTS["theme"]
    assert settings.get_int("ui/anim_ms") == DEFAULTS["ui/anim_ms"]
