"""ed25519 signature verification for signed org configs.

Crypto is an optional capability: it lives behind the ``aec[org-configs]``
extra so the core stays zero-dependency. pynacl (libsodium) is imported lazily;
a missing install raises :class:`OrgConfigCryptoUnavailable` with a clear
remediation message.

Supply-chain note: the pynacl pin in ``pyproject.toml`` is held at least one
release and three weeks behind the latest PyPI release (no known CVEs in the
pinned version), per project policy. Re-check OSV / pip-audit before bumping.
"""
from __future__ import annotations

import base64
import binascii
import hashlib

from .errors import OrgConfigError


class OrgConfigCryptoUnavailable(OrgConfigError):
    """pynacl is not installed; signed configs need ``pip install 'aec[org-configs]'``."""


def _load_nacl():
    try:
        import nacl.exceptions
        from nacl.signing import VerifyKey

        return VerifyKey, nacl.exceptions.BadSignatureError
    except ImportError as exc:
        raise OrgConfigCryptoUnavailable(
            "signed org configs require the crypto extra: pip install 'aec[org-configs]'"
        ) from exc


def decode_pubkey(pubkey_b64: str) -> bytes:
    """Decode a base64 ed25519 public key into its 32 raw bytes."""
    try:
        raw = base64.b64decode(pubkey_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise OrgConfigError(f"malformed base64 ed25519 public key: {exc}") from exc
    if len(raw) != 32:
        raise OrgConfigError(f"ed25519 public key must be 32 bytes, got {len(raw)}")
    return raw


def decode_signature(data: bytes) -> bytes:
    """Decode a detached signature: accept raw 64 bytes or base64-encoded text."""
    if len(data) == 64:
        return data
    try:
        raw = base64.b64decode(data.strip(), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise OrgConfigError(
            f"malformed signature (expected 64 raw bytes or base64): {exc}"
        ) from exc
    if len(raw) != 64:
        raise OrgConfigError(f"ed25519 signature must be 64 bytes, got {len(raw)}")
    return raw


def verify_detached(pubkey_raw: bytes, signature: bytes, message: bytes) -> bool:
    """Return True iff ``signature`` is a valid ed25519 sig over ``message``."""
    verify_key_cls, bad_signature_error = _load_nacl()
    try:
        verify_key_cls(pubkey_raw).verify(message, signature)
        return True
    except bad_signature_error:
        return False


def fingerprint(pubkey_raw: bytes) -> str:
    """Stable, human-comparable fingerprint of a raw ed25519 public key."""
    digest = hashlib.sha256(pubkey_raw).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")
