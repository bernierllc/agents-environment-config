"""Tests for dns_anchor trust verification (well-known pubkey + detached sig)."""

import base64

import pytest

nacl_signing = pytest.importorskip("nacl.signing")

from aec.lib.org_config.crypto import fingerprint  # noqa: E402
from aec.lib.org_config.errors import OrgConfigTrustError  # noqa: E402
from aec.lib.org_config.trust import UnsignedConsent, verify_trust  # noqa: E402


@pytest.fixture
def signed():
    """Return (config_bytes, signature, pubkey_b64, fingerprint, fetcher)."""
    signing_key = nacl_signing.SigningKey.generate()
    pubkey_raw = bytes(signing_key.verify_key)
    config_bytes = b"the org config bytes"
    sig = signing_key.sign(config_bytes).signature
    pubkey_b64 = base64.b64encode(pubkey_raw).decode("ascii")
    fp = fingerprint(pubkey_raw)

    def fetcher(url):
        assert url == "https://acme.example/.well-known/aec-pubkey"
        return pubkey_b64.encode("ascii")

    return config_bytes, sig, pubkey_b64, fp, fetcher


def _consent():
    return UnsignedConsent(acknowledged=False)


def test_dns_anchor_verifies_and_returns_fingerprint(signed):
    config_bytes, sig, _pubkey_b64, fp, fetcher = signed
    result = verify_trust(
        trust_mode="dns_anchor",
        config_bytes=config_bytes,
        consent=_consent(),
        signature=sig,
        dns_domain="acme.example",
        pubkey_fetcher=fetcher,
    )
    assert result.trust_mode == "dns_anchor"
    assert result.acknowledged is True
    assert result.pubkey_fingerprint == fp


def test_dns_anchor_rejects_tampered_config(signed):
    _config_bytes, sig, _pubkey_b64, _fp, fetcher = signed
    with pytest.raises(OrgConfigTrustError, match="signature verification failed"):
        verify_trust(
            trust_mode="dns_anchor",
            config_bytes=b"tampered config bytes",
            consent=_consent(),
            signature=sig,
            dns_domain="acme.example",
            pubkey_fetcher=fetcher,
        )


def test_dns_anchor_pin_mismatch_demands_rotate(signed):
    config_bytes, sig, _pubkey_b64, _fp, fetcher = signed
    with pytest.raises(OrgConfigTrustError, match="trust-rotate"):
        verify_trust(
            trust_mode="dns_anchor",
            config_bytes=config_bytes,
            consent=_consent(),
            signature=sig,
            dns_domain="acme.example",
            pubkey_fetcher=fetcher,
            pinned_fingerprint="SHA256:something-else",
        )


def test_dns_anchor_requires_domain(signed):
    config_bytes, sig, _pubkey_b64, _fp, _fetcher = signed
    with pytest.raises(OrgConfigTrustError, match="dns_domain"):
        verify_trust(
            trust_mode="dns_anchor",
            config_bytes=config_bytes,
            consent=_consent(),
            signature=sig,
            dns_domain=None,
        )


def test_dns_anchor_requires_signature(signed):
    config_bytes, _sig, _pubkey_b64, _fp, fetcher = signed
    with pytest.raises(OrgConfigTrustError, match="signature"):
        verify_trust(
            trust_mode="dns_anchor",
            config_bytes=config_bytes,
            consent=_consent(),
            signature=None,
            dns_domain="acme.example",
            pubkey_fetcher=fetcher,
        )
