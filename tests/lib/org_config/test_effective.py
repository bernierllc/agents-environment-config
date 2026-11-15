"""Tests for effective (merged, conflict-resolved) org policy."""

from pathlib import Path

import pytest

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


_RULE_TMPL = """---
schema_version: "1.0"
org_id: "{oid}"
org_name: "{oid}"
config_version: "1.0.0"
trust:
  mode: "unsigned"
---

sources:
  default: {{ skills: keep, rules: keep, agents: keep, mcps: keep }}
  custom:
    - id: "{oid}-catalog"
      url: "https://example.com/{oid}-catalog.git"
      ref: "main"
      contributes: ["rules"]

items:
  skills: {{}}
  rules:
    "shared-rule":
      source: "{source}"
      stance: {stance}{version}
  agents: {{}}
  mcps: {{}}
"""

SUBJECT = "rules/shared-rule"


def _orgs(home, *specs):
    """specs: (org_id, stance, source or None for the org's own catalog, version or None)."""
    orgs = home / ".aec" / "orgs"
    orgs.mkdir(parents=True, exist_ok=True)
    for oid, stance, source, version in specs:
        (orgs / f"{oid}.yaml").write_text(
            _RULE_TMPL.format(
                oid=oid,
                stance=stance,
                source=source or f"{oid}-catalog",
                version=f'\n      version: "{version}"' if version else "",
            ),
            encoding="utf-8",
        )


def _decide(paths, expected_kinds, decisions):
    """Record a decision for each conflict kind on the shared rule."""
    from aec.lib.org_config.reconcile import open_conflicts
    from aec.lib.org_config.resolutions import Resolution, save_resolution

    by_kind = {oc.conflict.kind: oc for oc in open_conflicts(paths) if oc.conflict.subject == SUBJECT}
    assert set(by_kind) == expected_kinds
    for kind, decision in decisions.items():
        save_resolution(
            paths,
            Resolution(
                conflict_id=by_kind[kind].conflict.conflict_id,
                decision=decision,
                input_hash=by_kind[kind].input_hash,
                decided_at="2026-05-24T00:00:00Z",
            ),
        )


# A blocker plus two installers on different sources is ONE conflict: every org is a
# participant, so the blocking org can be honored (and its block applied).
def _blocker_and_two_installers(home):
    _orgs(home, ("acme", "required", None, None), ("globex", "blocked", None, None),
          ("initech", "required", None, None))


@pytest.mark.parametrize("winner, stance", [("globex", "blocked"), ("acme", "required"), ("initech", "required")])
def test_any_org_can_be_honored_when_a_blocker_meets_two_sources(tmp_path, winner, stance):
    _blocker_and_two_installers(tmp_path)
    paths = OrgPaths(home_dir=tmp_path)
    _decide(paths, {"stance"}, {"stance": f"honor:{winner}"})
    pol = effective_policy(paths)
    assert pol.items[SUBJECT][0] == winner
    assert pol.items[SUBJECT][1].stance.value == stance
    assert SUBJECT not in pol.held


def test_a_blocker_meeting_two_sources_is_held_until_decided(tmp_path):
    _blocker_and_two_installers(tmp_path)
    pol = effective_policy(OrgPaths(home_dir=tmp_path))
    assert SUBJECT not in pol.items
    assert SUBJECT in pol.held


# A source conflict and a version conflict on one item are two decisions about one item.
def _source_and_version_conflict(home):
    _orgs(home, ("acme", "required", "aec.default.rules", "1.0.0"),
          ("globex", "pinned", "aec.default.rules", "2.0.0"),
          ("initech", "required", None, None))


def test_an_item_with_two_open_conflicts_is_held_until_both_are_decided(tmp_path):
    _source_and_version_conflict(tmp_path)
    paths = OrgPaths(home_dir=tmp_path)
    _decide(paths, {"source", "version"}, {"source": "honor:acme"})
    pol = effective_policy(paths)
    assert SUBJECT not in pol.items
    assert SUBJECT in pol.held


@pytest.mark.parametrize("source_decision, version_decision", [("skip", "honor:acme"), ("honor:acme", "skip")])
def test_a_skip_on_either_conflict_leaves_the_item_alone(tmp_path, source_decision, version_decision):
    # Whichever conflict id sorts first, the answer is the same: the user said skip.
    _source_and_version_conflict(tmp_path)
    paths = OrgPaths(home_dir=tmp_path)
    _decide(paths, {"source", "version"}, {"source": source_decision, "version": version_decision})
    pol = effective_policy(paths)
    assert SUBJECT not in pol.items
    assert SUBJECT not in pol.held


@pytest.mark.parametrize("source_decision, version_decision", [("honor:initech", "honor:acme"), ("honor:acme", "honor:globex")])
def test_decisions_naming_different_orgs_stay_held(tmp_path, source_decision, version_decision):
    _source_and_version_conflict(tmp_path)
    paths = OrgPaths(home_dir=tmp_path)
    _decide(paths, {"source", "version"}, {"source": source_decision, "version": version_decision})
    pol = effective_policy(paths)
    assert SUBJECT not in pol.items
    assert SUBJECT in pol.held


def test_decisions_naming_the_same_org_apply_that_org(tmp_path):
    _source_and_version_conflict(tmp_path)
    paths = OrgPaths(home_dir=tmp_path)
    _decide(paths, {"source", "version"}, {"source": "honor:acme", "version": "honor:acme"})
    pol = effective_policy(paths)
    assert pol.items[SUBJECT][0] == "acme"
    assert SUBJECT not in pol.held


def test_no_orgs_is_empty(tmp_path):
    pol = effective_policy(OrgPaths(home_dir=tmp_path))
    assert pol.items == {}
    assert pol.preferences == {}
    assert pol.held == ()
