# Packaging

Build scripts for desktop targets. Releases are produced by `.github/workflows/build.yml` when a `v*` tag is pushed.

| Target | Release asset | Run |
|---|---|---|
| Linux | `SkayClearTux-*-x86_64.AppImage` | `chmod +x` then execute |
| Debian/Ubuntu | `SkayClearTux-*-amd64.deb` | `sudo apt install ./file.deb` |
| Fedora/RHEL | `SkayClearTux-*-x86_64.rpm` | `sudo dnf install ./file.rpm` |
| Windows | `SkayClearTux-windows.zip` | unzip and run `SkayClearTux.exe` |
| macOS | `SkayClearTux-*.dmg` | open the image and drag to Applications |

Unsigned macOS builds may need right-click, Open, then Open again.

## Layout

- `01-linux/`: AppImage, deb and rpm scripts.
- `02-windows/`: PowerShell build script and PyInstaller spec.
- `03-macos/`: build script, spec and optional notarization helper.
- `latest.json.example`: shape of the update manifest.

## Build locally

```sh
python -m pip install -e ".[build]"
pyinstaller --noconfirm --clean --windowed --name SkayClearTux \
  --add-data "skaycleartux/assets:skaycleartux/assets" \
  --exclude-module tkinter SkayClearTux.py
VERSION=1.5.3.2 bash packaging/01-linux/make_appimage.sh
VERSION=1.5.3.2 bash packaging/01-linux/make_deb.sh
VERSION=1.5.3.2 bash packaging/01-linux/make_rpm.sh
```

Windows: `powershell -ExecutionPolicy Bypass -File packaging\02-windows\build.ps1`.
macOS: `bash packaging/03-macos/build.sh`.

## Update manifest

The manifest is signed with Ed25519. Unsigned manifests are rejected by the app.

```json
{
  "version": "1.5.3.2",
  "url": "https://github.com/skayinray/SkayClearTux/releases/download/v1.5.3.2/SkayClearTux-1.5.3.2-x86_64.AppImage",
  "sha256": "64 hex characters",
  "notes": "Short release notes",
  "published": "2026-11-18",
  "signature": "base64 Ed25519 signature"
}
```

CI generates this file and signs it with `tools/sign_update.py`. Each artifact also gets a `.sig` file. See [SECURITY.md](../SECURITY.md).

To tag a release: `git tag v1.5.3.2 && git push --tags`.
