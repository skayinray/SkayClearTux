"""Release signing key and manifest verification for automatic updates."""
from __future__ import annotations

import base64
import binascii
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Raw 32-byte Ed25519 public key, base64 encoded. The private half lives only
# in the RELEASE_SIGNING_KEY GitHub Actions secret and is never shipped.
RELEASE_PUBLIC_KEY_B64 = "5KD4tzB9obPd8wPN6soWC10dsnoMqX6ln4Pyh5i38ng="

_PUBLIC_KEY = Ed25519PublicKey.from_public_bytes(
    base64.b64decode(RELEASE_PUBLIC_KEY_B64, validate=True)
)


def canonical_manifest_bytes(payload: dict) -> bytes:
    """Return the exact bytes a release manifest signature is computed over."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def verify_manifest(data: dict) -> None:
    """Verify an update manifest against the embedded release key.

    Raises ValueError with a readable message when the signature is missing,
    malformed or invalid. The caller must not use unsigned manifests.
    """
    if not isinstance(data, dict):
        raise ValueError("манифест обновлений повреждён")
    signature = data.get("signature")
    if not signature:
        raise ValueError("манифест обновлений не подписан")
    payload = {key: value for key, value in data.items() if key != "signature"}
    try:
        raw_signature = base64.b64decode(str(signature), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("неверный формат подписи манифеста") from exc
    try:
        _PUBLIC_KEY.verify(raw_signature, canonical_manifest_bytes(payload))
    except InvalidSignature as exc:
        raise ValueError("подпись манифеста обновлений недействительна") from exc
