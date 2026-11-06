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


class TestImportedFileIsCanonical:
    def test_claude_importing_agents_drops_claude(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# a\n")
        (tmp_path / "CLAUDE.md").write_text("# c\n\n@AGENTS.md\n")
        names = {t.path.name for t in discover_targets("project", tmp_path)}
        assert "AGENTS.md" in names
        assert "CLAUDE.md" not in names

    def test_import_of_unrelated_file_keeps_both(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# a\n")
        (tmp_path / "CLAUDE.md").write_text("@docs/other.md\n")
        names = {t.path.name for t in discover_targets("project", tmp_path)}
        assert {"AGENTS.md", "CLAUDE.md"} <= names

    def test_inline_import_is_detected(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# a\n")
        (tmp_path / "CLAUDE.md").write_text("See @AGENTS.md for shared instructions.\n")
        names = {t.path.name for t in discover_targets("project", tmp_path)}
        assert "CLAUDE.md" not in names

    def test_import_inside_code_fence_or_span_is_ignored(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# a\n")
        (tmp_path / "CLAUDE.md").write_text(
            "Example:\n\n```\n@AGENTS.md\n```\n\nOr inline `@AGENTS.md`.\n"
            "Mail me@AGENTS.md.example\n"
        )
        names = {t.path.name for t in discover_targets("project", tmp_path)}
        assert {"AGENTS.md", "CLAUDE.md"} <= names

    @pytest.mark.parametrize("body", [
        "```\n@AGENTS.md\n",                              # unterminated fence
        "````\n```\n@AGENTS.md\n```\n````\n",            # nested fence
        "~~~\n@AGENTS.md\n~~~\n",                        # tilde fence
        "  ```\n@AGENTS.md\n  ```\n",                    # indented fence
    ])
    def test_import_inside_any_fence_is_ignored(self, tmp_path, body):
        (tmp_path / "AGENTS.md").write_text("# a\n")
        (tmp_path / "CLAUDE.md").write_text(body)
        names = {t.path.name for t in discover_targets("project", tmp_path)}
        assert {"AGENTS.md", "CLAUDE.md"} <= names

    def test_unresolvable_tilde_user_is_prose_not_a_crash(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# a\n")
        (tmp_path / "CLAUDE.md").write_text("ping @~nosuchuser-xyz about it\n")
        names = {t.path.name for t in discover_targets("project", tmp_path)}
        assert {"AGENTS.md", "CLAUDE.md"} <= names

    @pytest.mark.parametrize("body", ["Example:\n\n    @AGENTS.md\n", "\t@AGENTS.md\n"])
    def test_indented_code_block_is_ignored(self, tmp_path, body):
        (tmp_path / "AGENTS.md").write_text("# a\n")
        (tmp_path / "CLAUDE.md").write_text(body)
        names = {t.path.name for t in discover_targets("project", tmp_path)}
        assert {"AGENTS.md", "CLAUDE.md"} <= names

    def test_double_backtick_span_is_ignored(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# a\n")
        (tmp_path / "CLAUDE.md").write_text("Use ``@AGENTS.md`` to import.\n")
        names = {t.path.name for t in discover_targets("project", tmp_path)}
        assert {"AGENTS.md", "CLAUDE.md"} <= names

    def test_agent_without_import_support_keeps_its_file(self, tmp_path):
        (tmp_path / "GEMINI.md").write_text("# g\n")
        (tmp_path / "AGENTS.md").write_text("See @GEMINI.md for Gemini guidance.\n")
        names = {t.path.name for t in discover_targets("project", tmp_path)}
        assert {"AGENTS.md", "GEMINI.md"} <= names

    def test_trailing_punctuation_is_stripped(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# a\n")
        (tmp_path / "CLAUDE.md").write_text("(see @AGENTS.md).\n")
        names = {t.path.name for t in discover_targets("project", tmp_path)}
        assert "CLAUDE.md" not in names


class TestCanonicalize:
    def test_chain_resolves_to_last_file(self, tmp_path):
        from aec.lib.agent_blurb.targets import canonicalize

        (tmp_path / "QWEN.md").write_text("# q\n")
        (tmp_path / "GEMINI.md").write_text("@QWEN.md\n")
        (tmp_path / "CLAUDE.md").write_text("@GEMINI.md\n")
        existing = discover_targets("project", tmp_path, canonical=False)
        selected = [t for t in existing if t.path.name != "QWEN.md"]
        got = canonicalize(selected, existing)
        assert [t.path.name for t in got] == ["QWEN.md"]

    def test_explicit_importer_resolves_to_imported_target(self, tmp_path):
        from aec.lib.agent_blurb.targets import canonicalize

        (tmp_path / "AGENTS.md").write_text("# a\n")
        (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n")
        existing = discover_targets("project", tmp_path, canonical=False)
        claude = [t for t in existing if t.path.name == "CLAUDE.md"]
        got = canonicalize(claude, existing)
        assert [t.path.name for t in got] == ["AGENTS.md"]

    def test_selecting_importer_and_imported_dedupes(self, tmp_path):
        from aec.lib.agent_blurb.targets import canonicalize

        (tmp_path / "AGENTS.md").write_text("# a\n")
        (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n")
        existing = discover_targets("project", tmp_path, canonical=False)
        got = canonicalize(existing, existing)
        assert [t.path.name for t in got] == ["AGENTS.md"]
