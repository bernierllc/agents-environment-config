"""Tests for v1 → v2 manifest migration."""

import json
import pytest
from pathlib import Path


@pytest.fixture
def migration_env(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()

    v1 = {
        "manifestVersion": 1,
        "installedAt": "2026-03-30T00:00:00Z",
        "updatedAt": "2026-03-30T00:00:00Z",
        "skills": {
            "verification-writer": {"version": "1.0.0", "contentHash": "sha256:abc", "installedAt": "2026-03-30T00:00:00Z"},
            "commit": {"version": "1.0.0", "contentHash": "sha256:def", "installedAt": "2026-03-30T00:00:00Z"},
        }
    }
    (aec_home / "installed-skills.json").write_text(json.dumps(v1))
    return aec_home


class TestMigration:
    def test_migrates_v1_skills_to_v2_global(self, migration_env):
        from aec.lib.manifest_v2 import migrate_v1_to_v2
        v1_path = migration_env / "installed-skills.json"
        m = migrate_v1_to_v2(v1_path)
        assert m["manifestVersion"] == 2
        assert "verification-writer" in m["global"]["skills"]
        assert "commit" in m["global"]["skills"]
        assert m["global"]["skills"]["verification-writer"]["version"] == "1.0.0"

    def test_auto_migration_creates_v2(self, migration_env):
        from aec.lib.manifest_v2 import auto_migrate
        v2_path = migration_env / "installed-manifest.json"
        v1_path = migration_env / "installed-skills.json"
        assert not v2_path.exists()
        assert v1_path.exists()
        m = auto_migrate(v2_path, v1_path)
        assert m["manifestVersion"] == 2
        assert "verification-writer" in m["global"]["skills"]
        # v2 file should now exist on disk
        assert v2_path.exists()

    def test_auto_migrate_prefers_existing_v2(self, migration_env):
        from aec.lib.manifest_v2 import auto_migrate, save_manifest
        v2_path = migration_env / "installed-manifest.json"
        v1_path = migration_env / "installed-skills.json"
        # Create a v2 with different data
        v2_data = {"manifestVersion": 2, "updatedAt": "", "lastUpdateCheck": None,
                    "global": {"skills": {"custom-skill": {"version": "3.0.0"}}, "rules": {}, "agents": {}},
                    "repos": {}}
        save_manifest(v2_data, v2_path)
        m = auto_migrate(v2_path, v1_path)
        # Should load v2, not migrate from v1
        assert "custom-skill" in m["global"]["skills"]
        assert "verification-writer" not in m["global"]["skills"]

    def test_auto_migrate_handles_neither_existing(self, temp_dir):
        from aec.lib.manifest_v2 import auto_migrate
        v2_path = temp_dir / "v2.json"
        v1_path = temp_dir / "v1.json"
        m = auto_migrate(v2_path, v1_path)
        assert m["manifestVersion"] == 2
        assert m["global"]["skills"] == {}

    def test_preserves_content_hash(self, migration_env):
        from aec.lib.manifest_v2 import migrate_v1_to_v2
        v1_path = migration_env / "installed-skills.json"
        m = migrate_v1_to_v2(v1_path)
        assert m["global"]["skills"]["verification-writer"]["contentHash"] == "sha256:abc"
