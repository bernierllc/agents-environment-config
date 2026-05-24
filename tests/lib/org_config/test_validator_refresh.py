"""Tests for Phase 2c schema/validator additions: refresh.ttl_hours + url checks."""

import base64

import pytest

from aec.lib.org_config.errors import OrgConfigValidationError
from aec.lib.org_config.validator import validate_org_config


def _fm(trust=None):
    return {
        "schema_version": "1.0",
        "org_id": "acme",
        "org_name": "Acme",
        "config_version": "1.0.0",
        "trust": trust or {"mode": "unsigned"},
    }


def _body(refresh=None):
    body = {"sources": {"default": {}}, "items": {}}
    if refresh is not None:
        body["refresh"] = refresh
    return body


def test_refresh_ttl_defaults_to_none():
    cfg = validate_org_config(_fm(), _body())
    assert cfg.refresh_ttl_hours is None


def test_refresh_ttl_accepted():
    cfg = validate_org_config(_fm(), _body(refresh={"ttl_hours": 24}))
    assert cfg.refresh_ttl_hours == 24


def test_refresh_ttl_rejects_zero():
    with pytest.raises(OrgConfigValidationError, match="refresh.ttl_hours"):
        validate_org_config(_fm(), _body(refresh={"ttl_hours": 0}))


def test_refresh_ttl_rejects_negative():
    with pytest.raises(OrgConfigValidationError, match="refresh.ttl_hours"):
        validate_org_config(_fm(), _body(refresh={"ttl_hours": -5}))


def test_refresh_ttl_rejects_non_int():
    with pytest.raises(OrgConfigValidationError, match="refresh.ttl_hours"):
        validate_org_config(_fm(), _body(refresh={"ttl_hours": "soon"}))


def test_pinned_key_accepts_https_pubkey_url():
    trust = {"mode": "pinned_key", "pubkey_url": "https://acme.example/pubkey"}
    cfg = validate_org_config(_fm(trust=trust), _body())
    assert cfg.trust_pubkey_url == "https://acme.example/pubkey"


def test_pinned_key_rejects_non_https_pubkey_url():
    trust = {"mode": "pinned_key", "pubkey_url": "http://acme.example/pubkey"}
    with pytest.raises(OrgConfigValidationError, match="trust.pubkey_url"):
        validate_org_config(_fm(trust=trust), _body())


def test_rejects_non_https_signature_url():
    pubkey = base64.b64encode(b"x" * 32).decode()
    trust = {
        "mode": "pinned_key",
        "pubkey": pubkey,
        "signature_url": "http://acme.example/sig",
    }
    with pytest.raises(OrgConfigValidationError, match="trust.signature_url"):
        validate_org_config(_fm(trust=trust), _body())
