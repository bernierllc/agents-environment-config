"""Tests for pinned_key trust verification (Phase 2a)."""

import base64

import pytest

nacl_signing = pytest.importorskip("nacl.signing")

from aec.lib.org_config.crypto import fingerprint  # noqa: E402
from aec.lib.org_config.errors import OrgConfigTrustError  # noqa: E402
from aec.lib.org_config.trust import UnsignedConsent, verify_trust  # noqa: E402


@pytest.fixture
def signed_config():
    signing_key = nacl_signing.SigningKey.generate()
    pubkey_raw = bytes(signing_key.verify_key)
    config_bytes = b"---\norg_id: acme\n---\nitems: {}\n"
    sig = signing_key.sign(config_bytes).signature
    return {
        "config_bytes": config_bytes,
        "pubkey_b64": base64.b64encode(pubkey_raw).decode(),
        "signature": sig,
        "fingerprint": fingerprint(pubkey_raw),
    }


def _consent():
    return UnsignedConsent(acknowledged=True)


def test_valid_signature_passes_and_returns_fingerprint(signed_config):
    result = verify_trust(
        trust_mode="pinned_key",
        config_bytes=signed_config["config_bytes"],
        consent=_consent(),
        pubkey_b64=signed_config["pubkey_b64"],
        signature=signed_config["signature"],
    )
    assert result.trust_mode == "pinned_key"
    assert result.pubkey_fingerprint == signed_config["fingerprint"]


def test_tampered_config_fails(signed_config):
    with pytest.raises(OrgConfigTrustError, match="signature verification failed"):
        verify_trust(
            trust_mode="pinned_key",
            config_bytes=signed_config["config_bytes"] + b"tampered",
            consent=_consent(),
            pubkey_b64=signed_config["pubkey_b64"],
            signature=signed_config["signature"],
        )


def test_matching_pinned_fingerprint_passes(signed_config):
    result = verify_trust(
        trust_mode="pinned_key",
        config_bytes=signed_config["config_bytes"],
        consent=_consent(),
        pubkey_b64=signed_config["pubkey_b64"],
        signature=signed_config["signature"],
        pinned_fingerprint=signed_config["fingerprint"],
    )
    assert result.pubkey_fingerprint == signed_config["fingerprint"]


def test_rotated_key_halts_until_acknowledged(signed_config):
    with pytest.raises(OrgConfigTrustError, match="trust-rotate"):
        verify_trust(
            trust_mode="pinned_key",
            config_bytes=signed_config["config_bytes"],
            consent=_consent(),
            pubkey_b64=signed_config["pubkey_b64"],
            signature=signed_config["signature"],
            pinned_fingerprint="SHA256:some-other-pinned-key",
        )


def test_missing_signature_errors(signed_config):
    with pytest.raises(OrgConfigTrustError, match="detached signature"):
        verify_trust(
            trust_mode="pinned_key",
            config_bytes=signed_config["config_bytes"],
            consent=_consent(),
            pubkey_b64=signed_config["pubkey_b64"],
            signature=None,
        )


def test_missing_pubkey_errors(signed_config):
    with pytest.raises(OrgConfigTrustError, match="pubkey"):
        verify_trust(
            trust_mode="pinned_key",
            config_bytes=signed_config["config_bytes"],
            consent=_consent(),
            pubkey_b64=None,
            signature=signed_config["signature"],
        )
