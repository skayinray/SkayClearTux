"""Sign and verify SkayClearTux release manifests and artifacts.

Usage:
    python tools/sign_update.py manifest unsigned.json latest.json
    python tools/sign_update.py file dist/app.AppImage
    python tools/sign_update.py verify-file dist/app.AppImage dist/app.AppImage.sig

The signing key is read from RELEASE_SIGNING_KEY (base64-encoded PKCS8 PEM).
Verification uses the public key embedded in skaycleartux.release_key.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skaycleartux.release_key import canonical_manifest_bytes, verify_manifest  # noqa: E402


def _private_key() -> Ed25519PrivateKey:
    encoded = os.environ.get("RELEASE_SIGNING_KEY", "").strip()
    if not encoded:
        raise SystemExit("RELEASE_SIGNING_KEY is not set")
    try:
        pem = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise SystemExit(f"RELEASE_SIGNING_KEY is not valid base64: {exc}") from exc
    try:
        key = serialization.load_pem_private_key(pem, password=None)
    except Exception as exc:
        raise SystemExit(f"RELEASE_SIGNING_KEY is not a valid PEM key: {exc}") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit("RELEASE_SIGNING_KEY must be an Ed25519 private key")
    return key


def sign_manifest(source: Path, destination: Path) -> None:
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("manifest must be a JSON object")
    payload = {key: value for key, value in data.items() if key != "signature"}
    signature = _private_key().sign(canonical_manifest_bytes(payload))
    payload["signature"] = base64.b64encode(signature).decode("ascii")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"signed manifest: {destination}")


def sign_file(path: Path) -> None:
    signature = _private_key().sign(path.read_bytes())
    output = path.with_name(path.name + ".sig")
    output.write_text(base64.b64encode(signature).decode("ascii") + "\n", encoding="ascii")
    print(f"signed file: {path} -> {output}")


def verify_file(path: Path, signature_path: Path) -> None:
    from skaycleartux.release_key import _PUBLIC_KEY

    signature = base64.b64decode(signature_path.read_text(encoding="ascii").strip(), validate=True)
    _PUBLIC_KEY.verify(signature, path.read_bytes())
    print(f"signature OK: {path}")


def verify_manifest_file(path: Path) -> None:
    verify_manifest(json.loads(path.read_text(encoding="utf-8")))
    print(f"manifest signature OK: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest = subparsers.add_parser("manifest")
    manifest.add_argument("source", type=Path)
    manifest.add_argument("destination", type=Path)

    sign = subparsers.add_parser("file")
    sign.add_argument("paths", type=Path, nargs="+")

    verify = subparsers.add_parser("verify-file")
    verify.add_argument("path", type=Path)
    verify.add_argument("signature", type=Path)

    verify_m = subparsers.add_parser("verify-manifest")
    verify_m.add_argument("path", type=Path)

    args = parser.parse_args()
    if args.command == "manifest":
        sign_manifest(args.source, args.destination)
    elif args.command == "file":
        for path in args.paths:
            if path.is_file():
                sign_file(path)
    elif args.command == "verify-file":
        verify_file(args.path, args.signature)
    elif args.command == "verify-manifest":
        verify_manifest_file(args.path)


if __name__ == "__main__":
    main()
