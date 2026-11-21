# Windows build

Requires Windows 10/11 and Python 3.11+. The release asset is `SkayClearTux-windows.zip`; unzip it and run `SkayClearTux.exe`.

System pages use native tools: `winget`/`choco`, Windows services, `ipconfig`/`netstat`, WMI, Task Scheduler and Event Log. Linux-only pages are shown as unavailable.

## Build

```bat
packaging\02-windows\build.bat
```

or:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\02-windows\build.ps1
```

The script creates `.venv-win`, installs PySide6 Essentials, PyInstaller and Pillow, generates `tux.ico` and builds the onedir bundle from `SkayClearTux.spec`. Zip the whole `dist\SkayClearTux` directory.

For a single-file build, replace the `COLLECT` block in the spec, or run:

```bat
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name SkayClearTux ^
  --add-data "skaycleartux/assets;skaycleartux/assets" ^
  --icon skaycleartux/assets/tux.ico ^
  --exclude-module tkinter SkayClearTux.py
```

Windows uses `;` as the `--add-data` separator. An optional Inno Setup script can wrap `dist\SkayClearTux` into an installer.

Authenticode signing needs a commercial certificate and is not configured. Release integrity is covered by the Ed25519 `.sig` files described in `SECURITY.md`.
