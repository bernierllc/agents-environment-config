"""Tests for apply_org_policy orchestration: mode, lockout, held summary (A5)."""

import dataclasses
from pathlib import Path

import aec.commands.org as org_cmd
from aec.lib import preferences
from aec.lib.org_config.apply import apply_org_policy
from aec.lib.org_config.paths import OrgPaths
from aec.lib.org_config.state import read_state, write_state

TMPL = """---
schema_version: "1.0"
org_id: "{oid}"
org_name: "{oid}"
config_version: "1.0.0"
trust:
  mode: "unsigned"
---

sources:
  default: {{ skills: keep, rules: keep, agents: keep, mcps: keep }}
  custom: []

install:
  mode: "{mode}"
  preferences:
    projects_dir: "{projects_dir}"

items:
  skills:
    "foo":
      source: "aec.default.skills"
      stance: {foo_stance}
  rules: {{}}
  agents: {{}}
  mcps: {{}}
"""


def _write(home, oid, *, mode="managed", projects_dir="~/work", foo_stance="required"):
    orgs = home / ".aec" / "orgs"
    orgs.mkdir(parents=True, exist_ok=True)
    (orgs / f"{oid}.yaml").write_text(
        TMPL.format(oid=oid, mode=mode, projects_dir=projects_dir, foo_stance=foo_stance),
        encoding="utf-8",
    )


def _enroll(home, monkeypatch, oid, **kw):
    monkeypatch.setattr(Path, "home", lambda: home)
    cfg = home / f"{oid}.yaml"
    _write(home, oid, **kw)
    # Write into orgs dir via perform_enroll so state exists.
    src = home / "src.yaml"
    src.write_text((home / ".aec" / "orgs" / f"{oid}.yaml").read_text(), encoding="utf-8")
    org_cmd.perform_enroll(str(src), allow_unsigned=True)


def _prefs_redirect(tmp_path, monkeypatch):
    monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", tmp_path / "preferences.json")
    monkeypatch.setattr("aec.lib.preferences.AEC_HOME", tmp_path)


def test_managed_applies_silently(tmp_path, monkeypatch):
    _prefs_redirect(tmp_path, monkeypatch)
    _enroll(tmp_path, monkeypatch, "acme", mode="managed", projects_dir="~/work/acme")
    paths = OrgPaths(home_dir=tmp_path)

    outcome = apply_org_policy(paths, now="2026-05-24T00:00:00Z")

    assert outcome.skipped_reason is None
    assert "projects_dir" in outcome.preferences_applied
    assert preferences.load_preferences()["settings"]["projects_dir"] == "~/work/acme"


def test_guided_declined_makes_no_changes(tmp_path, monkeypatch):
    _prefs_redirect(tmp_path, monkeypatch)
    _enroll(tmp_path, monkeypatch, "acme", mode="guided", projects_dir="~/work/acme")
    paths = OrgPaths(home_dir=tmp_path)

    outcome = apply_org_policy(paths, confirm=lambda policy: False, now="2026-05-24T00:00:00Z")

    assert outcome.skipped_reason == "declined"
    assert "projects_dir" not in preferences.load_preferences().get("settings", {})


def test_guided_accepted_applies(tmp_path, monkeypatch):
    _prefs_redirect(tmp_path, monkeypatch)
    _enroll(tmp_path, monkeypatch, "acme", mode="guided", projects_dir="~/work/acme")
    paths = OrgPaths(home_dir=tmp_path)

    outcome = apply_org_policy(paths, confirm=lambda policy: True, now="2026-05-24T00:00:00Z")

    assert outcome.skipped_reason is None
    assert preferences.load_preferences()["settings"]["projects_dir"] == "~/work/acme"


def test_lockout_refuses_apply(tmp_path, monkeypatch):
    _prefs_redirect(tmp_path, monkeypatch)
    _enroll(tmp_path, monkeypatch, "acme", mode="managed", projects_dir="~/work/acme")
    paths = OrgPaths(home_dir=tmp_path)
    st = read_state(paths, "acme")
    write_state(
        paths,
        dataclasses.replace(
            st,
            key_rotation_pending={
                "detected_at": "2026-01-01T00:00:00Z",
                "new_fingerprint": "SHA256:x",
                "old_fingerprint": "SHA256:y",
            },
        ),
    )

    outcome = apply_org_policy(paths, now="2026-05-24T00:00:00Z")

    assert outcome.skipped_reason == "locked"
    assert "projects_dir" not in preferences.load_preferences().get("settings", {})


def test_held_items_surface_in_outcome(tmp_path, monkeypatch):
    _prefs_redirect(tmp_path, monkeypatch)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _write(tmp_path, "acme", mode="managed", foo_stance="required", projects_dir="~/a")
    _write(tmp_path, "globex", mode="managed", foo_stance="blocked", projects_dir="~/a")
    paths = OrgPaths(home_dir=tmp_path)

    outcome = apply_org_policy(paths, now="2026-05-24T00:00:00Z")

    assert "skills/foo" in outcome.held
