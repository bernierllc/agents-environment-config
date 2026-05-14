"""Tests for agent-blurb JSON config (source of truth per scope)."""

import json
import pytest

from aec.lib.agent_blurb.config import (
    CONFIG_FILENAME,
    SCHEMA_VERSION,
    config_path,
    load_config,
    new_skeleton,
    save_config,
)


class TestConfigPath:
    def test_project_path(self, tmp_path):
        assert config_path(scope="project", root=tmp_path) == tmp_path / ".aec" / "agent-blurb.json"

    def test_global_path(self, mock_home):
        from aec.lib.agent_blurb.config import config_path
        assert config_path(scope="global") == mock_home / ".aec" / "agent-blurb.json"

    def test_invalid_scope_raises(self, tmp_path):
        with pytest.raises(ValueError):
            config_path(scope="nope", root=tmp_path)


class TestSkeleton:
    def test_new_skeleton_balanced(self):
        c = new_skeleton(scope="project", profile="balanced", aec_version="2.37.4")
        assert c["schema"] == SCHEMA_VERSION
        assert c["scope"] == "project"
        assert c["profile"] == "balanced"
        assert c["aec_version_last_write"] == "2.37.4"
        assert c["matrix"]["skills"]["additive"] == "auto"
        assert c["targets"] == []

    def test_new_skeleton_custom_matrix(self):
        matrix = {"agents": {"additive": "auto"}}
        c = new_skeleton(scope="global", profile="custom", aec_version="2.37.4",
                         matrix_override=matrix)
        assert c["profile"] == "custom"
        assert c["matrix"]["agents"]["additive"] == "auto"

    def test_new_skeleton_custom_unknown_key_raises(self):
        with pytest.raises(ValueError, match="Unknown matrix item types"):
            new_skeleton(scope="global", profile="custom", aec_version="2.37.4",
                         matrix_override={"agnts": {"additive": "auto"}})


class TestLoadSave:
    def test_round_trip(self, tmp_path):
        c = new_skeleton(scope="project", profile="balanced", aec_version="2.37.4")
        save_config(c, scope="project", root=tmp_path)
        loaded = load_config(scope="project", root=tmp_path)
        assert loaded == c

    def test_load_missing_returns_none(self, tmp_path):
        assert load_config(scope="project", root=tmp_path) is None

    def test_save_creates_parent_dir(self, tmp_path):
        c = new_skeleton(scope="project", profile="balanced", aec_version="2.37.4")
        save_config(c, scope="project", root=tmp_path)
        assert (tmp_path / ".aec" / "agent-blurb.json").exists()

    def test_corrupt_json_raises(self, tmp_path):
        path = tmp_path / ".aec" / "agent-blurb.json"
        path.parent.mkdir()
        path.write_text("{not valid json")
        with pytest.raises(json.JSONDecodeError):
            load_config(scope="project", root=tmp_path)

    def test_target_record_round_trip(self, tmp_path):
        c = new_skeleton(scope="project", profile="balanced", aec_version="2.37.4")
        c["targets"].append({
            "agent_key": "claude",
            "path": "CLAUDE.md",
            "template_hash": "abc123",
            "content_hash": "def456",
            "written_at": "2026-05-12T14:03:00Z",
        })
        save_config(c, scope="project", root=tmp_path)
        loaded = load_config(scope="project", root=tmp_path)
        assert loaded["targets"][0]["agent_key"] == "claude"
        assert loaded["targets"][0]["path"] == "CLAUDE.md"

    def test_filename_constant(self):
        assert CONFIG_FILENAME == "agent-blurb.json"

    def test_load_non_object_raises(self, tmp_path):
        path = tmp_path / ".aec" / "agent-blurb.json"
        path.parent.mkdir()
        path.write_text("[1, 2, 3]")
        with pytest.raises(ValueError, match="not a JSON object"):
            load_config(scope="project", root=tmp_path)

    def test_load_wrong_schema_version_raises(self, tmp_path):
        path = tmp_path / ".aec" / "agent-blurb.json"
        path.parent.mkdir()
        path.write_text('{"schema": 999, "scope": "project"}')
        with pytest.raises(ValueError, match="schema"):
            load_config(scope="project", root=tmp_path)
