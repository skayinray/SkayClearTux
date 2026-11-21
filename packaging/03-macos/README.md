# macOS build

Builds `SkayClearTux.app` and a `.dmg`. Requires macOS with Xcode Command Line Tools and Python 3.11+.

```sh
bash packaging/03-macos/build.sh
```

The script creates `.venv-mac`, installs PySide6 Essentials, PyInstaller and Pillow, generates the `.icns` icon, builds the app from `SkayClearTux-macos.spec` and packs the dmg.

System pages use Homebrew, `launchctl`, `diskutil`, `system_profiler`, `pmset`, `ioreg`, `log show` and `lsof`. Kernel module and tweak pages are unavailable on macOS.

## First run of an unsigned build

Right-click the app in Finder, choose Open, then confirm Open in the dialog. Alternatively:

```sh
xattr -dr com.apple.quarantine /Applications/SkayClearTux.app
```

See `docs/images/macos-first-run.png`.

## Signing and notarization

`sign-and-notarize.sh` supports ad-hoc signing without an Apple account, and full Developer ID signing plus notarization when credentials are supplied:

```sh
export IDENTITY="Developer ID Application: NAME (TEAMID)"
export APPLE_ID="you@example.com"
export TEAM_ID="TEAMID"
export APP_PASSWORD="app-specific-password"
bash packaging/03-macos/sign-and-notarize.sh
```

It uses `entitlements.plist` for the Python/PySide6 dylib exceptions. A Developer ID certificate and Apple ID credentials are not stored in the repository. Until they are configured, CI publishes an unsigned dmg.

For Intel + Apple Silicon, build with a universal2 Python and `pyinstaller --target-arch universal2 --noconfirm --clean SkayClearTux-macos.spec`.
