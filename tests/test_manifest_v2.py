"""Tests for v2 manifest (global + per-repo tracking)."""

import json

import pytest
from pathlib import Path


@pytest.fixture
def manifest_path(temp_dir):
    return temp_dir / "installed-manifest.json"


@pytest.fixture
def v1_manifest_path(temp_dir):
    path = temp_dir / "installed-skills.json"
    path.write_text(json.dumps({
        "manifestVersion": 1,
        "installedAt": "2026-03-30T00:00:00Z",
        "updatedAt": "2026-03-30T00:00:00Z",
        "skills": {
            "verification-writer": {
                "version": "1.0.0",
                "contentHash": "sha256:abc",
                "installedAt": "2026-03-30T00:00:00Z",
                "source": "agents-environment-config",
            }
        }
    }))
    return path


class TestLoadManifestV2:
    def test_returns_empty_when_missing(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest
        m = load_manifest(manifest_path)
        assert m["manifestVersion"] == 2
        assert m["global"]["skills"] == {}
        assert m["global"]["rules"] == {}
        assert m["global"]["agents"] == {}
        assert m["repos"] == {}

    def test_loads_existing_v2(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest, save_manifest
        m = load_manifest(manifest_path)
        m["global"]["skills"]["test"] = {"version": "1.0.0"}
        save_manifest(m, manifest_path)
        loaded = load_manifest(manifest_path)
        assert loaded["global"]["skills"]["test"]["version"] == "1.0.0"


class TestSaveManifestV2:
    def test_creates_parent_dirs(self, temp_dir):
        from aec.lib.manifest_v2 import load_manifest, save_manifest
        path = temp_dir / "nested" / "dir" / "manifest.json"
        m = load_manifest(path)
        save_manifest(m, path)
        assert path.exists()

    def test_updates_timestamp(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest, save_manifest
        m = load_manifest(manifest_path)
        save_manifest(m, manifest_path)
        loaded = load_manifest(manifest_path)
        assert "updatedAt" in loaded


class TestManifestOperations:
    def test_record_global_install(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest, record_install, save_manifest
        m = load_manifest(manifest_path)
        record_install(m, scope="global", item_type="skills", name="my-skill",
                       version="2.0.0", content_hash="sha256:xyz")
        save_manifest(m, manifest_path)
        loaded = load_manifest(manifest_path)
        assert "my-skill" in loaded["global"]["skills"]
        assert loaded["global"]["skills"]["my-skill"]["version"] == "2.0.0"

    def test_record_repo_install(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest, record_install, save_manifest
        m = load_manifest(manifest_path)
        repo = "/Users/test/projects/my-app"
        record_install(m, scope=repo, item_type="skills", name="my-skill",
                       version="2.0.0", content_hash="sha256:xyz")
        save_manifest(m, manifest_path)
        loaded = load_manifest(manifest_path)
        assert repo in loaded["repos"]
        assert "my-skill" in loaded["repos"][repo]["skills"]

    def test_remove_global_install(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest, record_install, remove_install, save_manifest
        m = load_manifest(manifest_path)
        record_install(m, scope="global", item_type="skills", name="my-skill",
                       version="1.0.0", content_hash="sha256:abc")
        remove_install(m, scope="global", item_type="skills", name="my-skill")
        save_manifest(m, manifest_path)
        loaded = load_manifest(manifest_path)
        assert "my-skill" not in loaded["global"]["skills"]

    def test_get_installed_items(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest, record_install, get_installed
        m = load_manifest(manifest_path)
        record_install(m, scope="global", item_type="skills", name="a", version="1.0.0")
        record_install(m, scope="global", item_type="skills", name="b", version="2.0.0")
        record_install(m, scope="global", item_type="agents", name="c", version="1.0.0")
        skills = get_installed(m, scope="global", item_type="skills")
        assert set(skills.keys()) == {"a", "b"}

    def test_uses_absolute_paths_for_repos(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest, record_install, save_manifest
        m = load_manifest(manifest_path)
        record_install(m, scope="/Users/test/app", item_type="skills", name="x", version="1.0.0")
        save_manifest(m, manifest_path)
        raw = json.loads(manifest_path.read_text())
        repo_keys = list(raw["repos"].keys())
        assert all(k.startswith("/") for k in repo_keys)


class TestMigrateV1:
    def test_migrates_skills_to_global(self, v1_manifest_path, manifest_path):
        from aec.lib.manifest_v2 import migrate_v1_to_v2
        m = migrate_v1_to_v2(v1_manifest_path)
        assert m["manifestVersion"] == 2
        assert "verification-writer" in m["global"]["skills"]
        assert m["global"]["skills"]["verification-writer"]["version"] == "1.0.0"

    def test_handles_missing_v1(self, temp_dir, manifest_path):
        from aec.lib.manifest_v2 import migrate_v1_to_v2
        missing = temp_dir / "nonexistent.json"
        m = migrate_v1_to_v2(missing)
        assert m["manifestVersion"] == 2
        assert m["global"]["skills"] == {}


class TestAutoMigrate:
    def test_auto_migration_on_load(self, temp_dir, v1_manifest_path):
        from aec.lib.manifest_v2 import auto_migrate
        v2_path = temp_dir / "installed-manifest.json"
        assert not v2_path.exists()
        assert v1_manifest_path.exists()
        m = auto_migrate(v2_path, v1_manifest_path)
        assert m["manifestVersion"] == 2
        assert "verification-writer" in m["global"]["skills"]


class TestStaleness:
    def test_stale_when_never_checked(self):
        from aec.lib.manifest_v2 import is_stale
        assert is_stale({"lastUpdateCheck": None}) is True

    def test_not_stale_when_recent(self):
        from aec.lib.manifest_v2 import is_stale
        from datetime import datetime, timezone
        assert is_stale({"lastUpdateCheck": datetime.now(timezone.utc).isoformat()}) is False


class TestGetAllRepoScopes:
    def test_returns_empty_when_no_repos(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest, get_all_repo_scopes
        m = load_manifest(manifest_path)
        assert get_all_repo_scopes(m) == []

    def test_returns_repo_paths(self, manifest_path):
        from aec.lib.manifest_v2 import load_manifest, record_install, get_all_repo_scopes
        m = load_manifest(manifest_path)
        record_install(m, scope="/Users/test/app1", item_type="skills", name="x", version="1.0.0")
        record_install(m, scope="/Users/test/app2", item_type="rules", name="y", version="1.0.0")
        scopes = get_all_repo_scopes(m)
        assert set(scopes) == {"/Users/test/app1", "/Users/test/app2"}


class TestRecordUpdateCheck:
    def test_sets_last_update_check(self):
        from aec.lib.manifest_v2 import record_update_check
        m = {"lastUpdateCheck": None}
        record_update_check(m)
        assert m["lastUpdateCheck"] is not None
