"""Tests for ed25519 signature verification (requires the org-configs extra)."""

import base64

import pytest

nacl_signing = pytest.importorskip("nacl.signing")

from aec.lib.org_config.crypto import (  # noqa: E402
    OrgConfigError,
    decode_pubkey,
    decode_signature,
    fingerprint,
    verify_detached,
)


@pytest.fixture
def keypair():
    signing_key = nacl_signing.SigningKey.generate()
    verify_key = signing_key.verify_key
    return signing_key, bytes(verify_key)


def test_verify_detached_accepts_valid_signature(keypair):
    signing_key, pubkey_raw = keypair
    message = b"the org config bytes"
    sig = signing_key.sign(message).signature
    assert verify_detached(pubkey_raw, sig, message) is True


def test_verify_detached_rejects_tampered_message(keypair):
    signing_key, pubkey_raw = keypair
    sig = signing_key.sign(b"original").signature
    assert verify_detached(pubkey_raw, sig, b"tampered") is False


def test_verify_detached_rejects_wrong_key(keypair):
    signing_key, _ = keypair
    other_pubkey = bytes(nacl_signing.SigningKey.generate().verify_key)
    sig = signing_key.sign(b"msg").signature
    assert verify_detached(other_pubkey, sig, b"msg") is False


def test_decode_pubkey_round_trip(keypair):
    _, pubkey_raw = keypair
    b64 = base64.b64encode(pubkey_raw).decode()
    assert decode_pubkey(b64) == pubkey_raw


def test_decode_pubkey_rejects_wrong_length():
    with pytest.raises(OrgConfigError):
        decode_pubkey(base64.b64encode(b"too-short").decode())


def test_decode_signature_accepts_raw_and_base64(keypair):
    signing_key, _ = keypair
    sig = signing_key.sign(b"msg").signature
    assert decode_signature(sig) == sig
    assert decode_signature(base64.b64encode(sig)) == sig


def test_fingerprint_is_stable_and_prefixed(keypair):
    _, pubkey_raw = keypair
    fp = fingerprint(pubkey_raw)
    assert fp.startswith("SHA256:")
    assert fp == fingerprint(pubkey_raw)
