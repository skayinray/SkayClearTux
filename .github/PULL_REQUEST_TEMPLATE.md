<!-- Describe the change. Keep the checklist. -->

## What changed

<!-- Short summary and motivation. Link the issue if there is one. -->

Closes #

## How it was tested

<!-- Commands and results, for example:
     python -m pytest -q
     QT_QPA_PLATFORM=offscreen python tools/smoke_test.py
-->

## Checklist

- [ ] Branch is based on current `main`
- [ ] `python -m compileall -q skaycleartux SkayClearTux.py`
- [ ] `python -m pytest -q`
- [ ] `QT_QPA_PLATFORM=offscreen python tools/smoke_test.py`
- [ ] `python -m ruff check skaycleartux tests tools`
- [ ] System calls go through `skaycleartux/backends/`, no `shell=True`
- [ ] Docs updated if behavior changed

## Screenshots (for UI changes)

<!-- Drag images here -->
