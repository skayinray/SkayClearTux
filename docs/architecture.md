# Architecture

SkayClearTux is a PySide6 desktop app. Python 3.11+, PySide6 Essentials and cryptography are the only runtime dependencies.

```text
SkayClearTux.py
    -> skaycleartux/__main__.py
        -> main_window.py       window, navigation, update banner
            -> pages.py         generic page widgets and Worker(QThread)
            -> extra_pages.py   utilities, notes, hashes, backup, chess host
            -> tools_pages.py   processes, services, network, packages
            -> palette.py       Ctrl+K command palette
            -> backends/        OS-specific implementations
            -> updater.py       signed update check and install
```

Screens are registered in `main_window.py` and grouped into seven sections. Each page builds its own widgets; long-running work goes through `Worker` so the UI thread stays responsive.

## Backends

`skaycleartux/backends/` selects an implementation at runtime (`linux.py`, `macos.py`, `windows.py`). Common methods live in `base.py`; unsupported calls return a `NOT_AVAILABLE` result that the UI shows as disabled. Commands are argument lists with timeouts, never `shell=True`.

## Chess

`chess_widget.py` renders the board with `QPainter` and caches pixmaps at device pixel ratio. `chess_engine.py` runs a time-bounded negamax search with alpha-beta pruning in a `QThread`. Premoves are validated again before being applied. Ratings and settings are stored with `QSettings`.

## Updates

`updater.py` fetches `latest.json` over HTTPS, verifies its Ed25519 signature against `release_key.py`, checks the SHA-256 digest during download, replaces the AppImage atomically and restarts. Certificate verification is never disabled.

## Packaging

PyInstaller builds an onedir bundle. Linux scripts wrap it into AppImage, deb and rpm; Windows produces a zip; macOS produces a dmg. Release signing is described in `SECURITY.md`.
