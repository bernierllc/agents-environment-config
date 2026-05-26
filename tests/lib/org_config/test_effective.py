"""Tests for effective (merged, conflict-resolved) org policy."""

from pathlib import Path

import aec.commands.org as org_cmd
from aec.lib.org_config.effective import effective_policy
from aec.lib.org_config.paths import OrgPaths

ITEM_TMPL = """---
schema_version: "1.0"
org_id: "{oid}"
org_name: "{oid}"
config_version: "1.0.0"
trust:
  mode: "unsigned"
---

sources:
  default: {{ skills: {skills_stance}, rules: keep, agents: keep, mcps: keep }}
  custom: []

install:
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


def _write(home, oid, *, foo_stance="required", skills_stance="keep", projects_dir="~/work"):
    orgs = home / ".aec" / "orgs"
    orgs.mkdir(parents=True, exist_ok=True)
    (orgs / f"{oid}.yaml").write_text(
        ITEM_TMPL.format(
            oid=oid, foo_stance=foo_stance, skills_stance=skills_stance, projects_dir=projects_dir
        ),
        encoding="utf-8",
    )


def test_single_org_passthrough(tmp_path):
    _write(tmp_path, "acme", foo_stance="required")
    pol = effective_policy(OrgPaths(home_dir=tmp_path))
    assert "skills/foo" in pol.items
    assert pol.items["skills/foo"][0] == "acme"
    assert pol.preferences["projects_dir"] == "~/work"
    assert pol.held == ()


def test_two_orgs_agree_merges(tmp_path):
    _write(tmp_path, "acme", foo_stance="required", projects_dir="~/same")
    _write(tmp_path, "globex", foo_stance="required", projects_dir="~/same")
    pol = effective_policy(OrgPaths(home_dir=tmp_path))
    assert "skills/foo" in pol.items
    assert pol.preferences["projects_dir"] == "~/same"
    assert pol.held == ()


def test_open_stance_conflict_holds_item(tmp_path):
    _write(tmp_path, "acme", foo_stance="required")
    _write(tmp_path, "globex", foo_stance="blocked")
    pol = effective_policy(OrgPaths(home_dir=tmp_path))
    assert "skills/foo" not in pol.items
    assert "skills/foo" in pol.held


def test_open_preference_conflict_holds_pref(tmp_path):
    _write(tmp_path, "acme", projects_dir="~/work/acme")
    _write(tmp_path, "globex", projects_dir="~/code")
    pol = effective_policy(OrgPaths(home_dir=tmp_path))
    assert "projects_dir" not in pol.preferences
    assert "preference.projects_dir" in pol.held


def test_resolved_honor_picks_winner(tmp_path):
    _write(tmp_path, "acme", foo_stance="required")
    _write(tmp_path, "globex", foo_stance="blocked")
    paths = OrgPaths(home_dir=tmp_path)
    # Resolve the stance conflict in acme's favor.
    from aec.lib.org_config.reconcile import open_conflicts
    from aec.lib.org_config.resolutions import Resolution, save_resolution

    stance = next(oc for oc in open_conflicts(paths) if oc.conflict.subject == "skills/foo")
    save_resolution(
        paths,
        Resolution(
            conflict_id=stance.conflict.conflict_id,
            decision="honor:acme",
            input_hash=stance.input_hash,
            decided_at="2026-05-24T00:00:00Z",
        ),
    )
    pol = effective_policy(paths)
    assert pol.items["skills/foo"][0] == "acme"
    assert pol.items["skills/foo"][1].stance.value == "required"
    assert "skills/foo" not in pol.held


def test_resolved_skip_drops_subject(tmp_path):
    _write(tmp_path, "acme", foo_stance="required")
    _write(tmp_path, "globex", foo_stance="blocked")
    paths = OrgPaths(home_dir=tmp_path)
    from aec.lib.org_config.reconcile import open_conflicts
    from aec.lib.org_config.resolutions import Resolution, save_resolution

    stance = next(oc for oc in open_conflicts(paths) if oc.conflict.subject == "skills/foo")
    save_resolution(
        paths,
        Resolution(
            conflict_id=stance.conflict.conflict_id,
            decision="skip",
            input_hash=stance.input_hash,
            decided_at="2026-05-24T00:00:00Z",
        ),
    )
    pol = effective_policy(paths)
    assert "skills/foo" not in pol.items
    assert "skills/foo" not in pol.held


def test_no_orgs_is_empty(tmp_path):
    pol = effective_policy(OrgPaths(home_dir=tmp_path))
    assert pol.items == {}
    assert pol.preferences == {}
    assert pol.held == ()
