# Security policy

Supported versions: 1.5.x. Older releases do not receive fixes.

## Reporting

Open a private report with "Report a vulnerability" in the repository Security tab, or email `officialidea78@gmail.com`. Include the version, OS and a short reproducer. Please do not open public issues for security bugs.

## Update verification

Release manifests (`latest.json`) are signed with Ed25519. The public key is in `skaycleartux/release_key.py`; the private key exists only in the GitHub Actions secret `RELEASE_SIGNING_KEY`. The updater verifies the signature over canonical JSON before using any field, requires a 64-character SHA-256 digest, and enforces HTTPS including after redirects. TLS certificate verification is never skipped.

Every release artifact also has a `.sig` file (base64 Ed25519 signature over the raw file). Verify one locally with:

```sh
python tools/sign_update.py verify-file SkayClearTux-1.5.3.2-x86_64.AppImage SkayClearTux-1.5.3.2-x86_64.AppImage.sig
python tools/sign_update.py verify-manifest latest.json
```

Windows Authenticode and macOS notarization require commercial certificates and are not currently configured. Unsigned platform packages are marked as such in the release notes. Do not treat them as a trust signal beyond the release signature.
