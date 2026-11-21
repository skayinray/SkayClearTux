# Release notes

Current release: 1.5.3.2.

- Menu and dashboard text now adapts to smaller screens.
- Chess freeze after a move is fixed.
- Release manifests and artifacts are signed with Ed25519; the updater verifies them before installing.
- Linux, Windows and macOS packages are built by CI.

AppImage, deb, rpm, Windows zip and macOS dmg are published on the Releases page. Windows Authenticode and macOS notarization are not configured, so those packages are unsigned by the OS. Their integrity is covered by the release signature; see [SECURITY.md](SECURITY.md).
