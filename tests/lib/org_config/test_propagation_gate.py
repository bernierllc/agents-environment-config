"""Tests for the per-invocation propagation gate + concurrency safety."""

import base64
import dataclasses
import threading
from pathlib import Path

import pytest

nacl_signing = pytest.importorskip("nacl.signing")

import aec.commands.org as org_cmd  # noqa: E402
from aec.lib.org_config.crypto import fingerprint  # noqa: E402
from aec.lib.org_config.paths import OrgPaths  # noqa: E402
from aec.lib.org_config.propagation import run_propagation_gate  # noqa: E402
from aec.lib.org_config.state import read_state, write_state  # noqa: E402

DNS_CONFIG = """---
schema_version: "1.0"
org_id: "acme"
org_name: "Acme"
config_version: "1.0.0"
trust:
  mode: "dns_anchor"
  dns_domain: "acme.example"
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


def _enroll_dns(tmp_path, monkeypatch, key):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        org_cmd, "_pubkey_fetcher", lambda url: base64.b64encode(bytes(key.verify_key))
    )
    cfg = tmp_path / "acme.yaml"
    cfg.write_text(DNS_CONFIG, encoding="utf-8")
    cfg.with_name("acme.yaml.sig").write_bytes(key.sign(DNS_CONFIG.encode("utf-8")).signature)
    org_cmd.perform_enroll(str(cfg), trust_fingerprint=True)


def _age_out(paths):
    """Backdate last_verified_at so the dns pubkey cache is stale."""
    st = read_state(paths, "acme")
    write_state(paths, dataclasses.replace(st, last_verified_at="2026-01-01T00:00:00Z"))


def test_gate_detects_dns_rotation_and_records_pending(tmp_path, monkeypatch):
    key1 = nacl_signing.SigningKey.generate()
    _enroll_dns(tmp_path, monkeypatch, key1)
    paths = OrgPaths(home_dir=tmp_path)
    _age_out(paths)

    key2 = nacl_signing.SigningKey.generate()
    fetch2 = lambda url: base64.b64encode(bytes(key2.verify_key))

    result = run_propagation_gate(
        paths, now="2026-05-24T00:00:00Z", pubkey_fetcher=fetch2
    )

    assert "acme" in result.rotations_detected
    st = read_state(paths, "acme")
    assert st.key_rotation_pending is not None
    assert st.key_rotation_pending["new_fingerprint"] == fingerprint(bytes(key2.verify_key))


def test_gate_no_rotation_when_key_unchanged(tmp_path, monkeypatch):
    key = nacl_signing.SigningKey.generate()
    _enroll_dns(tmp_path, monkeypatch, key)
    paths = OrgPaths(home_dir=tmp_path)
    _age_out(paths)

    fetch_same = lambda url: base64.b64encode(bytes(key.verify_key))
    result = run_propagation_gate(paths, now="2026-05-24T00:00:00Z", pubkey_fetcher=fetch_same)

    assert result.rotations_detected == []
    # cache age was refreshed
    assert read_state(paths, "acme").last_verified_at == "2026-05-24T00:00:00Z"


def test_gate_skips_fetch_when_cache_fresh(tmp_path, monkeypatch):
    key = nacl_signing.SigningKey.generate()
    _enroll_dns(tmp_path, monkeypatch, key)
    paths = OrgPaths(home_dir=tmp_path)
    # last_verified_at is "now" from enroll; cache is fresh -> no fetch.
    called = []

    def fetcher(url):
        called.append(url)
        return base64.b64encode(bytes(key.verify_key))

    run_propagation_gate(paths, pubkey_fetcher=fetcher)
    assert called == []


def test_gate_surfaces_locked_status(tmp_path, monkeypatch):
    key = nacl_signing.SigningKey.generate()
    _enroll_dns(tmp_path, monkeypatch, key)
    paths = OrgPaths(home_dir=tmp_path)
    st = read_state(paths, "acme")
    write_state(
        paths,
        dataclasses.replace(
            st,
            key_rotation_pending={
                "detected_at": "2026-01-01T00:00:00Z",
                "new_fingerprint": "SHA256:x",
                "old_fingerprint": st.pubkey_fingerprint,
            },
        ),
    )
    result = run_propagation_gate(paths, now="2026-05-24T00:00:00Z")
    assert "acme" in result.locked


def test_concurrent_state_writes_do_not_corrupt(tmp_path, monkeypatch):
    key = nacl_signing.SigningKey.generate()
    _enroll_dns(tmp_path, monkeypatch, key)
    paths = OrgPaths(home_dir=tmp_path)
    base = read_state(paths, "acme")

    def writer(version):
        write_state(paths, dataclasses.replace(base, config_version=version))

    threads = [threading.Thread(target=writer, args=(f"{i}.0.0",)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # State remains readable + valid JSON despite concurrent writers.
    final = read_state(paths, "acme")
    assert final is not None
    assert final.org_id == "acme"


def _make_legacy(paths, **changes):
    """Strip trust_dns_domain, as state written before the field existed."""
    st = read_state(paths, "acme")
    write_state(paths, dataclasses.replace(st, trust_dns_domain=None, **changes))


def test_migrate_backfills_local_domain_before_any_fetch(tmp_path, monkeypatch):
    key = nacl_signing.SigningKey.generate()
    _enroll_dns(tmp_path, monkeypatch, key)
    paths = OrgPaths(home_dir=tmp_path)
    _make_legacy(paths, last_verified_at="2026-01-01T00:00:00Z")
    seen = []

    def fetcher(url):
        # The backfill is already persisted when the first fetch happens.
        seen.append(read_state(paths, "acme").trust_dns_domain)
        return base64.b64encode(bytes(key.verify_key))

    run_propagation_gate(paths, now="2026-05-24T00:00:00Z", pubkey_fetcher=fetcher)

    assert seen == ["acme.example"]
    st = read_state(paths, "acme")
    assert st.trust_dns_domain == "acme.example" and st.pending is None


def test_migrate_hash_mismatch_is_trust_change_and_skips_rotation(tmp_path, monkeypatch):
    key = nacl_signing.SigningKey.generate()
    _enroll_dns(tmp_path, monkeypatch, key)
    paths = OrgPaths(home_dir=tmp_path)
    _make_legacy(paths, config_hash="sha256:not-the-on-disk-bytes",
                 last_verified_at="2026-01-01T00:00:00Z")

    def fetcher(url):
        raise AssertionError("no fetch while a trust_change is pending")

    result = run_propagation_gate(paths, now="2026-05-24T00:00:00Z", pubkey_fetcher=fetcher)

    assert result.rotations_detected == []
    st = read_state(paths, "acme")
    assert st.trust_dns_domain is None
    assert st.pending == {
        "kind": "trust_change",
        "from": {"trust_dns_domain": None},
        "to": {"trust_dns_domain": "acme.example"},
    }


def test_migrate_url_source_never_backfills(tmp_path, monkeypatch):
    key = nacl_signing.SigningKey.generate()
    _enroll_dns(tmp_path, monkeypatch, key)
    paths = OrgPaths(home_dir=tmp_path)
    _make_legacy(paths, source_of_record="url", source_url="https://acme.example/org.yaml")

    from aec.lib.org_config.discovery import migrate_state

    st = migrate_state(paths, "acme")
    assert st.trust_dns_domain is None and st.pending["kind"] == "trust_change"


def test_gate_uses_recorded_domain_not_edited_yaml(tmp_path, monkeypatch):
    key = nacl_signing.SigningKey.generate()
    _enroll_dns(tmp_path, monkeypatch, key)
    paths = OrgPaths(home_dir=tmp_path)
    st = read_state(paths, "acme")
    write_state(paths, dataclasses.replace(
        st, trust_dns_domain="acme.example", last_verified_at="2026-01-01T00:00:00Z"))
    cfg = paths.config_for("acme")
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("acme.example", "evil.example"),
                   encoding="utf-8")
    urls = []

    def fetcher(url):
        urls.append(url)
        return base64.b64encode(bytes(key.verify_key))

    run_propagation_gate(paths, now="2026-05-24T00:00:00Z", pubkey_fetcher=fetcher)
    assert urls == ["https://acme.example/.well-known/aec-pubkey"]
