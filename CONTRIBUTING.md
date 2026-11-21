# Contributing

Keep changes small and focused. Open an issue first for large features.

## Setup

```sh
python -m pip install -e ".[dev]"
python -m pytest -q
```

## Rules

- Python 3.11+, 100-column lines, `ruff check skaycleartux tests tools`.
- Never use `shell=True`. Run external commands as argument lists with timeouts.
- UI code imports only `QtCore`, `QtGui` and `QtWidgets` from PySide6 Essentials. Do not add Addons modules.
- New system actions need a backend method with a safe stub for unsupported OSes.
- Updater changes require tests for signatures, checksums and hostile URLs.

## Before opening a PR

- `python -m pytest -q`
- `QT_QPA_PLATFORM=offscreen python tools/smoke_test.py`
- Update the README if you change behavior or add a screen.

CI runs tests on Linux, macOS and Windows. Coverage must stay at or above 60% for the tested modules. Releases are built from tags by the release workflow; signing secrets are not available to forks.
