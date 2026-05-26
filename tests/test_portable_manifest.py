"""Tests for the portable manifest (aec export / aec apply serialization)."""

from pathlib import Path

import pytest

from aec.lib.portable_manifest import (
    PROJECTS_TOKEN,
    PortableManifestError,
    build_portable_manifest,
    dump_manifest,
    load_portable_manifest,
    relativize_repo_scope,
    resolve_repo_token,
)


def _v2_manifest(repo_path: str) -> dict:
    return {
        "manifestVersion": 2,
        "installedAt": "2026-05-01T00:00:00Z",
        "updatedAt": "2026-05-01T00:00:00Z",
        "lastUpdateCheck": None,
        "global": {
            "skills": {"my-skill": {"version": "1.2.0", "contentHash": "sha256:abc", "installedAt": "x"}},
            "rules": {"my-rule": {"version": "1.0.0", "contentHash": "", "installedAt": "x"}},
            "agents": {},
            "mcps": {"my-mcp": {"version": "0.3.0", "installedAt": "x", "package": "some-pip-pkg"}},
        },
        "repos": {
            repo_path: {
                "skills": {"repo-skill": {"version": "2.0.0", "contentHash": "", "installedAt": "x"}},
                "rules": {},
                "agents": {},
                "mcps": {},
            }
        },
    }


class TestBuildAndStrip:
    def test_strips_machine_specific_data(self, tmp_path):
        repo = str((tmp_path / "projects" / "my-app").resolve())
        manifest = _v2_manifest(repo)
        portable = build_portable_manifest(manifest, projects_dir=tmp_path / "projects")
        text = dump_manifest(portable)

        # no absolute paths, hashes, or timestamps leak into the portable file
        assert str(tmp_path) not in text
        assert "contentHash" not in text
        assert "installedAt" not in text
        assert "sha256" not in text

    def test_global_items_present(self, tmp_path):
        manifest = _v2_manifest(str((tmp_path / "projects" / "a").resolve()))
        portable = build_portable_manifest(manifest, projects_dir=tmp_path / "projects")
        skills = portable["global"]["skills"]
        assert {"name": "my-skill", "version": "1.2.0"} in skills
        mcp = portable["global"]["mcps"][0]
        assert mcp == {"name": "my-mcp", "version": "0.3.0", "package": "some-pip-pkg"}

    def test_repo_path_is_tokenized(self, tmp_path):
        repo = str((tmp_path / "projects" / "my-app").resolve())
        manifest = _v2_manifest(repo)
        portable = build_portable_manifest(manifest, projects_dir=tmp_path / "projects")
        assert portable["repos"][0]["path"] == f"{PROJECTS_TOKEN}/my-app"

    def test_latest_flag_overrides_versions(self, tmp_path):
        manifest = _v2_manifest(str((tmp_path / "projects" / "a").resolve()))
        portable = build_portable_manifest(manifest, latest=True, projects_dir=tmp_path / "projects")
        assert all(s["version"] == "latest" for s in portable["global"]["skills"])

    def test_no_repos_flag(self, tmp_path):
        manifest = _v2_manifest(str((tmp_path / "projects" / "a").resolve()))
        portable = build_portable_manifest(manifest, include_repos=False, projects_dir=tmp_path / "projects")
        assert "repos" not in portable


class TestRoundTrip:
    def test_dump_load_round_trip(self, tmp_path):
        manifest = _v2_manifest(str((tmp_path / "projects" / "a").resolve()))
        portable = build_portable_manifest(manifest, projects_dir=tmp_path / "projects")
        assert load_portable_manifest(dump_manifest(portable)) == portable

    def test_unknown_schema_version_rejected(self):
        with pytest.raises(PortableManifestError):
            load_portable_manifest('{"schemaVersion": 99}')

    def test_invalid_json_rejected(self):
        with pytest.raises(PortableManifestError):
            load_portable_manifest("not json{{")

    def test_non_object_rejected(self):
        with pytest.raises(PortableManifestError):
            load_portable_manifest("[1, 2, 3]")


class TestTokens:
    def test_relativize_under_projects(self, tmp_path):
        projects = tmp_path / "projects"
        repo = projects / "my-app"
        assert relativize_repo_scope(str(repo), projects) == f"{PROJECTS_TOKEN}/my-app"

    def test_relativize_outside_projects_uses_basename(self, tmp_path):
        repo = tmp_path / "elsewhere" / "weird-app"
        assert relativize_repo_scope(str(repo), tmp_path / "projects") == "weird-app"

    def test_resolve_projects_token(self, tmp_path):
        projects = tmp_path / "projects"
        resolved = resolve_repo_token(f"{PROJECTS_TOKEN}/my-app", projects_dir=projects)
        assert resolved == (projects / "my-app").resolve()

    def test_resolve_basename_against_tracked(self, tmp_path):
        repo = tmp_path / "code" / "my-app"
        resolved = resolve_repo_token("my-app", projects_dir=tmp_path / "projects", tracked_repos=[repo])
        assert resolved == repo.resolve()

    def test_resolve_basename_unmatched_returns_none(self, tmp_path):
        assert resolve_repo_token("ghost", projects_dir=tmp_path / "projects", tracked_repos=[]) is None

    def test_token_round_trip_across_machines(self, tmp_path):
        # machine 1 home -> token -> machine 2 home (different projects dir)
        home1 = tmp_path / "home1" / "projects"
        home2 = tmp_path / "home2" / "projects"
        token = relativize_repo_scope(str(home1 / "my-app"), home1)
        resolved = resolve_repo_token(token, projects_dir=home2)
        assert resolved == (home2 / "my-app").resolve()
