"""Tests for repo-scoped effective policy with project overlays (Phase 4a)."""
from __future__ import annotations

import textwrap

from aec.lib.org_config.effective import effective_policy, effective_policy_for_repo
from aec.lib.org_config.paths import OrgPaths


def _write(home, oid, body):
    orgs = home / ".aec" / "orgs"
    orgs.mkdir(parents=True, exist_ok=True)
    header = textwrap.dedent(
        f"""\
        ---
        schema_version: "1.0"
        org_id: "{oid}"
        org_name: "{oid}"
        config_version: "1.0.0"
        trust:
          mode: "unsigned"
        ---
        """
    )
    (orgs / f"{oid}.yaml").write_text(header + "\n" + textwrap.dedent(body), encoding="utf-8")


ACME_WITH_PROJECT = """\
sources:
  default: { skills: keep, rules: keep, agents: keep, mcps: keep }
  custom: []

items:
  skills:
    "base":
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
          "repo-only":
            source: "aec.default.skills"
            stance: required
          "base":
            source: "aec.default.skills"
            stance: blocked
      prompts:
        setup.track_current_repo: true
"""


def test_no_match_equals_base_policy(tmp_path):
    _write(tmp_path, "acme", ACME_WITH_PROJECT)
    paths = OrgPaths(home_dir=tmp_path)
    repo = effective_policy_for_repo(
        paths, repo_path="/some/other", git_remote="git@github.com:other/x.git"
    )
    base = effective_policy(paths)
    assert set(repo.items) == set(base.items)
    assert "skills/repo-only" not in repo.items


def test_matching_project_adds_repo_item(tmp_path):
    _write(tmp_path, "acme", ACME_WITH_PROJECT)
    paths = OrgPaths(home_dir=tmp_path)
    repo = effective_policy_for_repo(
        paths, repo_path="/w/backend", git_remote="git@github.com:acme/backend.git"
    )
    assert "skills/repo-only" in repo.items


def test_profile_overrides_base_stance(tmp_path):
    _write(tmp_path, "acme", ACME_WITH_PROJECT)
    paths = OrgPaths(home_dir=tmp_path)
    base = effective_policy(paths)
    assert base.items["skills/base"][1].stance.value == "required"
    repo = effective_policy_for_repo(
        paths, repo_path="/w/backend", git_remote="https://github.com/acme/backend"
    )
    # In-repo the base skill's stance is overridden to blocked by the profile.
    assert repo.items["skills/base"][1].stance.value == "blocked"


def test_profile_prompts_merged(tmp_path):
    _write(tmp_path, "acme", ACME_WITH_PROJECT)
    paths = OrgPaths(home_dir=tmp_path)
    repo = effective_policy_for_repo(
        paths, repo_path="/w/backend", git_remote="git@github.com:acme/backend.git"
    )
    assert repo.prompts.get("setup.track_current_repo") is True


GLOBEX_PROJECT_CONFLICT = """\
sources:
  default: { skills: keep, rules: keep, agents: keep, mcps: keep }
  custom: []

items:
  skills: {}
  rules: {}
  agents: {}
  mcps: {}

projects:
  - match:
      git_remote: "github.com:acme/backend"
    profile:
      items:
        skills:
          "base":
            source: "aec.default.skills"
            stance: blocked
"""


SIMPLE_REQUIRED = """\
sources:
  default: { skills: keep, rules: keep, agents: keep, mcps: keep }
  custom: []

items:
  skills:
    "base":
      source: "aec.default.skills"
      stance: required
  rules: {}
  agents: {}
  mcps: {}
"""


def test_cross_org_project_conflict_is_held(tmp_path):
    # acme requires skills/base globally; globex's project overlay blocks it here.
    _write(tmp_path, "acme", SIMPLE_REQUIRED)
    _write(tmp_path, "globex", GLOBEX_PROJECT_CONFLICT)
    paths = OrgPaths(home_dir=tmp_path)
    repo = effective_policy_for_repo(
        paths, repo_path="/w/backend", git_remote="git@github.com:acme/backend.git"
    )
    assert "skills/base" not in repo.items
    assert "skills/base" in repo.held
    # Outside the repo there is no conflict: globex declares nothing globally.
    base = effective_policy(paths)
    assert "skills/base" in base.items
