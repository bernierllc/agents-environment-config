"""Tests for url-sourced org-config refresh (Phase 2c.3)."""

from pathlib import Path

import pytest

import aec.commands.org as org_cmd  # noqa: E402
from aec.lib.org_config.paths import OrgPaths
from aec.lib.org_config.state import read_state

UNSIGNED_V1 = """---
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

UNSIGNED_V2 = UNSIGNED_V1.replace('config_version: "1.0.0"', 'config_version: "2.0.0"')

URL = "https://acme.example/acme.yaml"


def _serve(monkeypatch, body: bytes):
    monkeypatch.setattr(org_cmd, "_url_fetcher", lambda url: body)


def _enroll_url(monkeypatch, tmp_path, body: bytes):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _serve(monkeypatch, body)
    org_cmd.perform_enroll(URL, allow_unsigned=True)


def test_refresh_unchanged_is_noop(tmp_path, monkeypatch):
    _enroll_url(monkeypatch, tmp_path, UNSIGNED_V1.encode())
    paths = OrgPaths(home_dir=tmp_path)
    before = read_state(paths, "acme")

    results = org_cmd.refresh_url_sourced_orgs(paths)

    assert results == [("acme", "unchanged")]
    after = read_state(paths, "acme")
    assert after.config_hash == before.config_hash
    assert after.last_applied_at == before.last_applied_at


def test_refresh_updates_changed_config(tmp_path, monkeypatch):
    _enroll_url(monkeypatch, tmp_path, UNSIGNED_V1.encode())
    paths = OrgPaths(home_dir=tmp_path)
    old_hash = read_state(paths, "acme").config_hash

    _serve(monkeypatch, UNSIGNED_V2.encode())
    results = org_cmd.refresh_url_sourced_orgs(paths)

    assert results == [("acme", "updated")]
    after = read_state(paths, "acme")
    assert after.config_hash != old_hash
    assert after.config_version == "2.0.0"


def test_refresh_skips_local_orgs(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cfg = tmp_path / "acme.yaml"
    cfg.write_text(UNSIGNED_V1, encoding="utf-8")
    org_cmd.perform_enroll(str(cfg), allow_unsigned=True)

    paths = OrgPaths(home_dir=tmp_path)
    results = org_cmd.refresh_url_sourced_orgs(paths)
    assert results == []


def test_refresh_reports_fetch_failure(tmp_path, monkeypatch):
    _enroll_url(monkeypatch, tmp_path, UNSIGNED_V1.encode())
    paths = OrgPaths(home_dir=tmp_path)

    from aec.lib.org_config.errors import OrgConfigFetchError

    def boom(url):
        raise OrgConfigFetchError("connection refused")

    monkeypatch.setattr(org_cmd, "_url_fetcher", boom)
    results = org_cmd.refresh_url_sourced_orgs(paths)
    assert results[0][0] == "acme"
    assert "fetch failed" in results[0][1]
