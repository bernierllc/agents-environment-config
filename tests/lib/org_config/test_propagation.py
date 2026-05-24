"""Tests for org-config change/rotation detection primitives."""

import base64

import pytest

nacl_signing = pytest.importorskip("nacl.signing")

from aec.lib.org_config.crypto import fingerprint  # noqa: E402
from aec.lib.org_config.propagation import detect_dns_rotation, due_for_refresh  # noqa: E402


def test_due_for_refresh_none_ttl_never_due():
    assert due_for_refresh(
        last_verified_at="2026-01-01T00:00:00Z", ttl_hours=None, now="2026-05-24T00:00:00Z"
    ) is False


def test_due_for_refresh_elapsed_beyond_ttl():
    assert due_for_refresh(
        last_verified_at="2026-05-23T00:00:00Z", ttl_hours=24, now="2026-05-24T01:00:00Z"
    ) is True


def test_due_for_refresh_within_ttl():
    assert due_for_refresh(
        last_verified_at="2026-05-24T00:00:00Z", ttl_hours=24, now="2026-05-24T01:00:00Z"
    ) is False


def _pubkey_b64():
    pubkey_raw = bytes(nacl_signing.SigningKey.generate().verify_key)
    return base64.b64encode(pubkey_raw).decode("ascii"), fingerprint(pubkey_raw)


def test_no_rotation_when_fingerprint_matches():
    pubkey_b64, fp = _pubkey_b64()
    result = detect_dns_rotation(
        dns_domain="acme.example",
        pinned_fingerprint=fp,
        fetcher=lambda url: pubkey_b64.encode("ascii"),
        now="2026-05-24T00:00:00Z",
    )
    assert result is None


def test_rotation_flagged_when_fingerprint_differs():
    pubkey_b64, new_fp = _pubkey_b64()
    result = detect_dns_rotation(
        dns_domain="acme.example",
        pinned_fingerprint="SHA256:stale-old-key",
        fetcher=lambda url: pubkey_b64.encode("ascii"),
        now="2026-05-24T00:00:00Z",
    )
    assert result == {
        "detected_at": "2026-05-24T00:00:00Z",
        "new_fingerprint": new_fp,
        "old_fingerprint": "SHA256:stale-old-key",
    }


def test_no_pinned_fingerprint_is_noop():
    pubkey_b64, _fp = _pubkey_b64()
    called = []
    result = detect_dns_rotation(
        dns_domain="acme.example",
        pinned_fingerprint=None,
        fetcher=lambda url: called.append(url) or pubkey_b64.encode("ascii"),
        now="2026-05-24T00:00:00Z",
    )
    assert result is None
    assert called == []  # short-circuits without fetching


def test_builds_well_known_url():
    pubkey_b64, fp = _pubkey_b64()
    seen = {}

    def fetcher(url):
        seen["url"] = url
        return pubkey_b64.encode("ascii")

    detect_dns_rotation(
        dns_domain="acme.example",
        pinned_fingerprint=fp,
        fetcher=fetcher,
        now="2026-05-24T00:00:00Z",
    )
    assert seen["url"] == "https://acme.example/.well-known/aec-pubkey"
