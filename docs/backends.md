# Backend contract

`skaycleartux.backends.get_backend()` returns the implementation for the current OS. All backends expose the same methods and return plain values or simple dictionaries.

## Rules

- Run external tools as argument lists with `subprocess.run(..., timeout=...)` and `shell=False`.
- Return `NOT_AVAILABLE` for features the OS does not have. Never raise for a missing command.
- Never request root/administrator rights implicitly. Use the platform prompt only from an explicit user action.
- Parse output defensively. Truncate long command output before putting it in the UI.
- Keep per-OS quirks in the OS module, not in page code.

## Linux

Detects `pacman`, `apt`, `dnf`, `zypper` and `apk`. Uses `systemctl`, `journalctl`, `ip`, `ss`, `lsmod`, `lm-sensors`, SMART tools and XDG paths.

## macOS

Uses `brew`, `launchctl`, `log show`, `powermetrics`, `system_profiler` and diskutil/SMART where available. Some Linux-only pages are marked unavailable.

## Windows

Uses PowerShell/cmdlets, `winget`/`choco`, WMI/CIM, Event Log, `netstat` and known cache locations. Commands are started without a visible console window.

## Adding a method

1. Add a default implementation in `backends/base.py`.
2. Override it in each OS module where it makes sense.
3. Add tests with a fake runner in `tests/test_backend_*.py`.
4. Wire the UI through `SystemInfo` or the page helper, never directly to a backend module.
