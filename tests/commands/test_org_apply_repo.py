"""Repo-scoped apply of per-project overlays (Phase 4a)."""
import json
from pathlib import Path

import aec.commands.org as org_cmd
from aec.lib.manifest_v2 import load_manifest
from aec.lib.org_config.apply import apply_org_policy
from aec.lib.org_config.paths import OrgPaths

CONFIG_WITH_PROJECT = """---
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
    "base-skill":
      source: "aec.default.skills"
      stance: required
  rules: {}
  agents: {}
  mcps: {}

projects:
  - match:
      git_remote: "github.com:acme/backend"
    profile:
      items:
        skills:
          "repo-skill":
            source: "aec.default.skills"
            stance: required
"""

AVAIL = {
    "skills": {
        "base-skill": {"version": "1.0.0", "path": "base-skill"},
        "repo-skill": {"version": "1.0.0", "path": "repo-skill"},
    }
}


def _empty_manifest():
    return {
        "manifestVersion": 2,
        "installedAt": "x",
        "updatedAt": "x",
        "lastUpdateCheck": None,
        "global": {"skills": {}, "rules": {}, "agents": {}, "mcps": {}},
        "repos": {},
    }


def _seed_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    aec_home = tmp_path / ".agents-environment-config"
    aec_home.mkdir()
    (aec_home / "installed-manifest.json").write_text(json.dumps(_empty_manifest()))
    repo_skills = tmp_path / "catalog" / ".claude" / "skills"
    for nm in ("base-skill", "repo-skill"):
        s = repo_skills / nm
        s.mkdir(parents=True)
        (s / "SKILL.md").write_text(
            f"---\nname: {nm}\nversion: 1.0.0\ndescription: d\n---\n# s", encoding="utf-8"
        )
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    monkeypatch.setattr("aec.lib.sources.get_source_dirs", lambda: {"skills": repo_skills})
    monkeypatch.setattr(
        "aec.lib.sources.discover_available", lambda d, plural: AVAIL.get(plural, {})
    )
    return aec_home


def test_project_overlay_installs_at_repo_scope(tmp_path, monkeypatch):
    aec_home = _seed_catalog(tmp_path, monkeypatch)
    work = tmp_path / "work" / "backend"
    (work / ".claude" / "skills").mkdir(parents=True)

    src = tmp_path / "acme.yaml"
    src.write_text(CONFIG_WITH_PROJECT, encoding="utf-8")
    org_cmd.perform_enroll(str(src), allow_unsigned=True)

    outcome = apply_org_policy(
        OrgPaths(home_dir=tmp_path),
        now="2026-05-24T00:00:00Z",
        repo_path=str(work),
        git_remote="git@github.com:acme/backend.git",
    )
    assert outcome.skipped_reason is None

    # Global base skill installed at global scope.
    assert (tmp_path / ".claude" / "skills" / "base-skill" / "SKILL.md").exists()
    # Profile's repo-skill installed at repo scope.
    assert (work / ".claude" / "skills" / "repo-skill" / "SKILL.md").exists()

    m = load_manifest(aec_home / "installed-manifest.json")
    assert "base-skill" in m["global"]["skills"]
    assert "repo-skill" in m["repos"][str(work)]["skills"]
    # Base skill is not duplicated into repo scope.
    assert "base-skill" not in m["repos"].get(str(work), {}).get("skills", {})


def test_no_matching_repo_is_global_only(tmp_path, monkeypatch):
    aec_home = _seed_catalog(tmp_path, monkeypatch)
    src = tmp_path / "acme.yaml"
    src.write_text(CONFIG_WITH_PROJECT, encoding="utf-8")
    org_cmd.perform_enroll(str(src), allow_unsigned=True)

    outcome = apply_org_policy(
        OrgPaths(home_dir=tmp_path),
        now="2026-05-24T00:00:00Z",
        repo_path="/some/other",
        git_remote="git@github.com:other/x.git",
    )
    assert outcome.skipped_reason is None
    m = load_manifest(aec_home / "installed-manifest.json")
    assert "base-skill" in m["global"]["skills"]
    assert m["repos"] == {}
