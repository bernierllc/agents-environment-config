"""Tests for discovering which agent files exist per scope."""

import pytest

from aec.lib.agent_blurb.targets import AgentTarget, discover_targets


class TestDiscoverTargets:
    def test_project_scope_only_returns_existing(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# c\n")
        (tmp_path / "AGENTS.md").write_text("# a\n")
        targets = discover_targets(scope="project", root=tmp_path)
        paths = {t.path.name for t in targets}
        assert "CLAUDE.md" in paths
        assert "AGENTS.md" in paths
        assert "GEMINI.md" not in paths

    def test_global_scope(self, mock_home, monkeypatch):
        # configurable_instructions.HOME is captured at import time, so
        # monkeypatch it explicitly so the global path resolves under mock_home.
        monkeypatch.setattr("aec.lib.configurable_instructions.HOME", mock_home)
        claude_dir = mock_home / ".claude"
        claude_dir.mkdir()
        (claude_dir / "CLAUDE.md").write_text("# g\n")
        targets = discover_targets(scope="global")
        paths = [str(t.path) for t in targets]
        assert str(claude_dir / "CLAUDE.md") in paths

    def test_empty_when_no_files(self, tmp_path):
        targets = discover_targets(scope="project", root=tmp_path)
        assert targets == []

    def test_target_has_agent_key(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# c\n")
        targets = discover_targets(scope="project", root=tmp_path)
        assert isinstance(targets[0], AgentTarget)
        assert targets[0].agent_key == "claude"


class TestResolvePathForAgentKey:
    def test_project(self, tmp_path):
        from aec.lib.agent_blurb.targets import resolve_path_for_agent_key
        p = resolve_path_for_agent_key("claude", scope="project", root=tmp_path)
        assert p == tmp_path / "CLAUDE.md"

    def test_global(self, mock_home, monkeypatch):
        from aec.lib.agent_blurb.targets import resolve_path_for_agent_key
        monkeypatch.setattr("aec.lib.configurable_instructions.HOME", mock_home)
        p = resolve_path_for_agent_key("claude", scope="global")
        assert p.is_relative_to(mock_home)

    def test_unknown_agent_raises(self, tmp_path):
        from aec.lib.agent_blurb.targets import resolve_path_for_agent_key
        with pytest.raises(KeyError):
            resolve_path_for_agent_key(
                "not-a-real-agent", scope="project", root=tmp_path
            )
