"""End-to-end: an org that requires a skill installs it from a real catalog."""

import json
from pathlib import Path

import aec.commands.org as org_cmd
from aec.lib.manifest_v2 import load_manifest
from aec.lib.org_config.apply import apply_org_policy
from aec.lib.org_config.paths import OrgPaths

CONFIG = """---
schema_version: "1.0"
org_id: "acme"
org_name: "acme"
config_version: "1.0.0"
trust:
  mode: "unsigned"
---

sources:
  default: { skills: keep, rules: keep, agents: keep, mcps: keep }
  custom: []

install:
  mode: "managed"

items:
  skills:
    "my-skill":
      source: "aec.default.skills"
      stance: required
  rules: {}
  agents: {}
  mcps: {}
"""

AVAIL = {"skills": {"my-skill": {"version": "1.0.0", "path": "my-skill"}}}


def _empty_manifest():
    return {
        "manifestVersion": 2,
        "installedAt": "x",
        "updatedAt": "x",
        "lastUpdateCheck": None,
        "global": {"skills": {}, "rules": {}, "agents": {}, "mcps": {}},
        "repos": {},
    }


def test_required_item_is_installed_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Seed a real catalog with one installable skill.
    aec_home = tmp_path / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "installed-manifest.json").write_text(json.dumps(_empty_manifest()))
    repo_skills = tmp_path / "aec-repo" / ".claude" / "skills"
    skill = repo_skills / "my-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: my-skill\nversion: 1.0.0\ndescription: d\n---\n# s", encoding="utf-8"
    )
    (tmp_path / ".claude" / "skills").mkdir(parents=True)

    # Point the applier's catalog lookup at the seeded source dir.
    monkeypatch.setattr(
        "aec.lib.sources.get_source_dirs", lambda: {"skills": repo_skills}
    )
    monkeypatch.setattr(
        "aec.lib.sources.discover_available", lambda d, plural: AVAIL.get(plural, {})
    )

    # Enroll the org that requires my-skill.
    src = tmp_path / "acme.yaml"
    src.write_text(CONFIG, encoding="utf-8")
    org_cmd.perform_enroll(str(src), allow_unsigned=True)

    outcome = apply_org_policy(OrgPaths(home_dir=tmp_path), now="2026-05-24T00:00:00Z")

    assert outcome.skipped_reason is None
    assert outcome.applied_items == 1
    # Physically installed on disk...
    assert (tmp_path / ".claude" / "skills" / "my-skill" / "SKILL.md").exists()
    # ...and recorded in the manifest.
    m = load_manifest(aec_home / "installed-manifest.json")
    assert "my-skill" in m["global"]["skills"]
