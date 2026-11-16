"""Доступ к ресурсам, работает и из исходников, и из собранного бандла."""
from __future__ import annotations

import sys
from pathlib import Path


def assets_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "skaycleartux" / "assets"
    return Path(__file__).parent / "assets"


def asset(name: str) -> str:
    return str(assets_dir() / name)
