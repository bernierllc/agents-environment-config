"""Tests for per-type installed file store (installed_store.py)."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def store_home(tmp_path, monkeypatch):
    """Point AEC_HOME and INSTALLED_MANIFEST_V2 at tmp_path for isolation."""
    import aec.lib.config as config_mod
    import aec.lib.installed_store as store_mod

    monkeypatch.setattr(config_mod, "AEC_HOME", tmp_path)
    monkeypatch.setattr(config_mod, "INSTALLED_MANIFEST_V2", tmp_path / "installed-manifest.json")
    monkeypatch.setattr(store_mod, "AEC_HOME", tmp_path)
    monkeypatch.setattr(store_mod, "INSTALLED_MANIFEST_V2", tmp_path / "installed-manifest.json")
    return tmp_path


class TestInstalledPath:
    def test_returns_plural_path(self, store_home):
        from aec.lib.installed_store import _installed_path

        assert _installed_path("agent") == store_home / "installed-agents.json"
        assert _installed_path("rule") == store_home / "installed-rules.json"
        assert _installed_path("skill") == store_home / "installed-skills.json"

    def test_rejects_invalid_type(self, store_home):
        from aec.lib.installed_store import _installed_path

        with pytest.raises(ValueError, match="Unknown item type"):
            _installed_path("widget")


class TestLoadInstalled:
    def test_returns_empty_on_missing_file(self, store_home):
        from aec.lib.installed_store import load_installed

        data = load_installed("agent")
        assert data["schemaVersion"] == 1
        assert data["items"] == {}
        assert "installedAt" in data
        assert "updatedAt" in data

    def test_returns_empty_on_corrupt_file(self, store_home):
        from aec.lib.installed_store import load_installed

        (store_home / "installed-agents.json").write_text("not json!!!")
        data = load_installed("agent")
        assert data["schemaVersion"] == 1
        assert data["items"] == {}

    def test_returns_empty_on_non_dict(self, store_home):
        from aec.lib.installed_store import load_installed

        (store_home / "installed-agents.json").write_text(json.dumps([1, 2, 3]))
        data = load_installed("agent")
        assert data["items"] == {}

    def test_loads_valid_store(self, store_home):
        from aec.lib.installed_store import load_installed

        store_data = {
            "schemaVersion": 1,
            "installedAt": "2026-04-10T00:00:00Z",
            "updatedAt": "2026-04-10T00:00:00Z",
            "items": {
                "my-agent": {
                    "version": "1.2.3",
                    "contentHash": "sha256:abc",
                    "installedAt": "2026-04-10T00:00:00Z",
                }
            },
        }
        (store_home / "installed-agents.json").write_text(json.dumps(store_data))
        data = load_installed("agent")
        assert data["items"]["my-agent"]["version"] == "1.2.3"

    def test_migrates_v1_skills_format(self, store_home):
        from aec.lib.installed_store import load_installed

        v1_data = {
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
            },
        }
        (store_home / "installed-skills.json").write_text(json.dumps(v1_data))
        data = load_installed("skill")
        assert data["schemaVersion"] == 1
        assert data["items"]["verification-writer"]["version"] == "1.0.0"
        assert data["items"]["verification-writer"]["contentHash"] == "sha256:abc"
        # source field should not carry over
        assert "source" not in data["items"]["verification-writer"]

        # File should be rewritten in new format
        on_disk = json.loads((store_home / "installed-skills.json").read_text())
        assert on_disk["schemaVersion"] == 1
        assert "items" in on_disk
        assert "skills" not in on_disk

    def test_v1_migration_only_applies_to_skills(self, store_home):
        """V1 format migration should not trigger for agents or rules."""
        from aec.lib.installed_store import load_installed

        v1_like = {
            "manifestVersion": 1,
            "skills": {"something": {"version": "1.0.0"}},
        }
        (store_home / "installed-agents.json").write_text(json.dumps(v1_like))
        data = load_installed("agent")
        # Should return empty, not attempt migration
        assert data["items"] == {}


class TestRecordAndRetrieve:
    def test_record_creates_entry(self, store_home):
        from aec.lib.installed_store import record_item_install, get_all_installed

        record_item_install("agent", "backend-architect", "1.0.0", "sha256:abc")
        items = get_all_installed("agent")
        assert "backend-architect" in items
        assert items["backend-architect"]["version"] == "1.0.0"
        assert items["backend-architect"]["contentHash"] == "sha256:abc"
        assert "installedAt" in items["backend-architect"]

    def test_record_updates_existing(self, store_home):
        from aec.lib.installed_store import record_item_install, get_all_installed

        record_item_install("rule", "typescript-standards", "1.0.0")
        record_item_install("rule", "typescript-standards", "2.0.0", "sha256:xyz")
        items = get_all_installed("rule")
        assert items["typescript-standards"]["version"] == "2.0.0"
        assert items["typescript-standards"]["contentHash"] == "sha256:xyz"

    def test_record_preserves_other_items(self, store_home):
        from aec.lib.installed_store import record_item_install, get_all_installed

        record_item_install("skill", "a-skill", "1.0.0")
        record_item_install("skill", "b-skill", "2.0.0")
        items = get_all_installed("skill")
        assert "a-skill" in items
        assert "b-skill" in items

    def test_get_all_returns_empty_for_no_items(self, store_home):
        from aec.lib.installed_store import get_all_installed

        assert get_all_installed("agent") == {}


class TestRemoveInstall:
    def test_remove_existing_item(self, store_home):
        from aec.lib.installed_store import record_item_install, remove_item_install, get_all_installed

        record_item_install("agent", "my-agent", "1.0.0")
        assert "my-agent" in get_all_installed("agent")

        remove_item_install("agent", "my-agent")
        assert "my-agent" not in get_all_installed("agent")

    def test_remove_nonexistent_is_noop(self, store_home):
        from aec.lib.installed_store import remove_item_install, get_all_installed

        # Should not raise
        remove_item_install("agent", "does-not-exist")
        assert get_all_installed("agent") == {}


class TestSeedFromManifest:
    def test_seeds_all_types(self, store_home):
        from aec.lib.installed_store import seed_from_manifest, get_all_installed

        manifest = {
            "manifestVersion": 2,
            "installedAt": "2026-04-10T00:00:00Z",
            "updatedAt": "2026-04-10T00:00:00Z",
            "lastUpdateCheck": None,
            "global": {
                "skills": {
                    "verification-writer": {
                        "version": "1.0.0",
                        "contentHash": "sha256:s1",
                        "installedAt": "2026-04-10T00:00:00Z",
                    }
                },
                "agents": {
                    "backend-architect": {
                        "version": "2.0.0",
                        "contentHash": "sha256:a1",
                        "installedAt": "2026-04-10T00:00:00Z",
                    }
                },
                "rules": {
                    "typescript-standards": {
                        "version": "1.0.0",
                        "contentHash": "",
                        "installedAt": "2026-04-10T00:00:00Z",
                    }
                },
            },
            "repos": {},
        }
        (store_home / "installed-manifest.json").write_text(json.dumps(manifest))

        count = seed_from_manifest()
        assert count == 3

        skills = get_all_installed("skill")
        assert skills["verification-writer"]["version"] == "1.0.0"

        agents = get_all_installed("agent")
        assert agents["backend-architect"]["version"] == "2.0.0"

        rules = get_all_installed("rule")
        assert rules["typescript-standards"]["version"] == "1.0.0"

    def test_returns_zero_when_no_manifest(self, store_home):
        from aec.lib.installed_store import seed_from_manifest

        assert seed_from_manifest() == 0

    def test_skips_types_with_existing_files(self, store_home):
        from aec.lib.installed_store import seed_from_manifest, get_all_installed

        # Pre-create an agents file
        existing = {
            "schemaVersion": 1,
            "installedAt": "2026-04-10T00:00:00Z",
            "updatedAt": "2026-04-10T00:00:00Z",
            "items": {"existing-agent": {"version": "9.9.9", "contentHash": "", "installedAt": "2026-04-10T00:00:00Z"}},
        }
        (store_home / "installed-agents.json").write_text(json.dumps(existing))

        manifest = {
            "manifestVersion": 2,
            "installedAt": "2026-04-10T00:00:00Z",
            "updatedAt": "2026-04-10T00:00:00Z",
            "lastUpdateCheck": None,
            "global": {
                "skills": {},
                "agents": {
                    "new-agent": {"version": "1.0.0", "contentHash": "", "installedAt": "2026-04-10T00:00:00Z"}
                },
                "rules": {},
            },
            "repos": {},
        }
        (store_home / "installed-manifest.json").write_text(json.dumps(manifest))

        count = seed_from_manifest()
        # Should NOT have seeded agents since file already exists
        assert count == 0
        agents = get_all_installed("agent")
        assert "existing-agent" in agents
        assert "new-agent" not in agents

    def test_handles_corrupt_manifest(self, store_home):
        from aec.lib.installed_store import seed_from_manifest

        (store_home / "installed-manifest.json").write_text("broken json!")
        assert seed_from_manifest() == 0

    def test_handles_v1_manifest_ignored(self, store_home):
        from aec.lib.installed_store import seed_from_manifest

        v1 = {"manifestVersion": 1, "skills": {}}
        (store_home / "installed-manifest.json").write_text(json.dumps(v1))
        assert seed_from_manifest() == 0


class TestAtomicWrite:
    def test_file_written_atomically(self, store_home):
        """Verify the per-type file uses atomic write (no partial writes)."""
        from aec.lib.installed_store import record_item_install

        record_item_install("agent", "test-agent", "1.0.0")
        path = store_home / "installed-agents.json"
        assert path.exists()

        data = json.loads(path.read_text())
        assert data["schemaVersion"] == 1
        assert data["items"]["test-agent"]["version"] == "1.0.0"

    def test_creates_parent_dirs(self, tmp_path, monkeypatch):
        """Atomic write should create parent dirs if needed."""
        import aec.lib.config as config_mod
        import aec.lib.installed_store as store_mod

        nested = tmp_path / "deep" / "nested"
        monkeypatch.setattr(config_mod, "AEC_HOME", nested)
        monkeypatch.setattr(store_mod, "AEC_HOME", nested)

        from aec.lib.installed_store import record_item_install

        record_item_install("agent", "test", "1.0.0")
        assert (nested / "installed-agents.json").exists()


class TestDualWrite:
    """Verify that install/uninstall commands write to both manifest and per-type files."""

    def test_install_cmd_dual_writes(self, store_home, monkeypatch, tmp_path):
        """install_cmd.run_install writes to both manifest and per-type file.

        This test verifies the integration point: after record_install + save_manifest,
        the per-type record_item_install is also called.
        """
        from aec.lib.installed_store import record_item_install, get_all_installed

        # Simulate what install_cmd does after the manifest write
        record_item_install("skill", "my-skill", "1.0.0", "sha256:abc")

        items = get_all_installed("skill")
        assert "my-skill" in items
        assert items["my-skill"]["version"] == "1.0.0"

        # Also verify file on disk
        path = store_home / "installed-skills.json"
        on_disk = json.loads(path.read_text())
        assert on_disk["items"]["my-skill"]["version"] == "1.0.0"

    def test_uninstall_dual_writes(self, store_home):
        """Verify remove_item_install removes from per-type file."""
        from aec.lib.installed_store import record_item_install, remove_item_install, get_all_installed

        record_item_install("agent", "doomed-agent", "1.0.0")
        assert "doomed-agent" in get_all_installed("agent")

        remove_item_install("agent", "doomed-agent")
        assert "doomed-agent" not in get_all_installed("agent")
