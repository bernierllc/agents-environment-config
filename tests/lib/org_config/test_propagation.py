"""Tests for org-config change/rotation detection primitives."""

import base64
from pathlib import Path

import pytest

nacl_signing = pytest.importorskip("nacl.signing")

from aec.lib.org_config.crypto import fingerprint  # noqa: E402
from aec.lib.org_config.propagation import (  # noqa: E402
    detect_changes,
    detect_dns_rotation,
    due_for_refresh,
    policy_diff,
)
from aec.lib.org_config.paths import OrgPaths  # noqa: E402
from aec.lib.org_config.schema import ItemPolicy, OrgConfig, Stance  # noqa: E402


def _cfg(**over):
    base = dict(
        schema_version="1.0",
        org_id="acme",
        org_name="Acme",
        config_version="1.0.0",
        description=None,
        trust_mode="unsigned",
        default_sources={},
        custom_sources=[],
        items={"skills": {}, "rules": {}, "agents": {}, "mcps": {}},
        install_preferences={},
        install_prompts={},
        install_agents_enabled=[],
        install_agents_disabled=[],
        install_mode=None,
    )
    base.update(over)
    return OrgConfig(**base)


def _skill(name, stance, version=None):
    return {"skills": {name: ItemPolicy(source="aec.default.skills", stance=Stance(stance), version=version)},
            "rules": {}, "agents": {}, "mcps": {}}


MINIMAL = """---
schema_version: "1.0"
org_id: "acme"
org_name: "Acme"
config_version: "1.0.0"
trust:
  mode: "unsigned"
---

sources:
  default: { skills: keep, rules: keep, agents: keep, mcps: keep }
  custom: []

items:
  skills: {}
  rules: {}
  agents: {}
  mcps: {}
"""


def _enroll_local(tmp_path, monkeypatch, text=MINIMAL):
    import aec.commands.org as org_cmd

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg = tmp_path / "acme.yaml"
    cfg.write_text(text, encoding="utf-8")
    org_cmd.perform_enroll(str(cfg), allow_unsigned=True)


def test_detect_changes_unchanged(tmp_path, monkeypatch):
    _enroll_local(tmp_path, monkeypatch)
    changes = detect_changes(OrgPaths(home_dir=tmp_path))
    assert [(c.org_id, c.status) for c in changes] == [("acme", "unchanged")]


def test_detect_changes_changed(tmp_path, monkeypatch):
    _enroll_local(tmp_path, monkeypatch)
    paths = OrgPaths(home_dir=tmp_path)
    # Mutate the enrolled config on disk.
    paths.config_for("acme").write_text(
        MINIMAL.replace('config_version: "1.0.0"', 'config_version: "2.0.0"'), encoding="utf-8"
    )
    changes = detect_changes(paths)
    assert changes[0].status == "changed"
    assert changes[0].old_hash != changes[0].new_hash


def test_detect_changes_new_when_state_missing(tmp_path, monkeypatch):
    _enroll_local(tmp_path, monkeypatch)
    paths = OrgPaths(home_dir=tmp_path)
    paths.state_for("acme").unlink()
    changes = detect_changes(paths)
    assert changes[0].status == "new"
    assert changes[0].old_hash is None


def test_policy_diff_detects_item_and_mode_changes():
    old = _cfg(items=_skill("foo", "required"), install_mode="guided")
    new = _cfg(
        items=_skill("foo", "blocked"),
        install_mode="managed",
        default_sources={"skills": "replace"},
    )
    diff = policy_diff(old, new)
    assert diff.items_changed == ("skills/foo",)
    assert diff.install_mode_change == "guided->managed"
    assert any("skills" in s for s in diff.source_changes)
    assert not diff.is_empty()


def test_policy_diff_add_remove():
    old = _cfg(items=_skill("foo", "required"))
    new = _cfg(items=_skill("bar", "required"))
    diff = policy_diff(old, new)
    assert diff.items_added == ("skills/bar",)
    assert diff.items_removed == ("skills/foo",)


def test_policy_diff_empty_when_identical():
    old = _cfg(items=_skill("foo", "required"))
    new = _cfg(items=_skill("foo", "required"))
    assert policy_diff(old, new).is_empty()


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
