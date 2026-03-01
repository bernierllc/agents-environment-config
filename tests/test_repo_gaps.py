"""Tests for bash-parity gaps ported to Python CLI."""

import pytest
from pathlib import Path
from unittest.mock import patch


class TestSetupNoArgInteractive:
    """Test that setup prompts for project name when called with no args."""

    def test_setup_prompts_when_no_path(self, tmp_path, monkeypatch):
        """setup(path=None) prompts for project name via input()."""
        from aec.commands.repo import setup

        # Patch input() to provide a project name
        monkeypatch.setattr("builtins.input", lambda prompt: "my-project")
        # Patch the rest of setup to avoid side effects — just verify path resolves
        monkeypatch.setattr("aec.commands.repo.get_repo_root", lambda: tmp_path)
        monkeypatch.setattr("aec.commands.repo.load_env_file", lambda: None)
        monkeypatch.setattr("aec.commands.repo.AGENT_TOOLS_DIR", tmp_path / ".agent-tools")
        (tmp_path / ".agent-tools" / "rules" / "agents-environment-config").mkdir(parents=True)
        monkeypatch.setattr("aec.commands.repo.get_projects_dir", lambda: tmp_path)

        # The function should prompt and use "my-project" as path
        # It will fail later (directory doesn't exist, etc.) but won't raise SystemExit(1)
        # due to empty path
        try:
            setup(path=None, skip_raycast=True, dry_run=True)
        except SystemExit:
            pass  # Expected — project dir doesn't exist in dry_run

    def test_setup_exits_on_empty_input(self, tmp_path, monkeypatch):
        """setup(path=None) exits if user provides empty input."""
        from aec.commands.repo import setup

        monkeypatch.setattr("builtins.input", lambda prompt: "")
        monkeypatch.setattr("aec.commands.repo.load_env_file", lambda: None)

        with pytest.raises(SystemExit):
            setup(path=None)

    def test_setup_exits_on_eof(self, tmp_path, monkeypatch):
        """setup(path=None) exits on EOFError (piped input)."""
        from aec.commands.repo import setup

        def raise_eof(prompt):
            raise EOFError

        monkeypatch.setattr("builtins.input", raise_eof)
        monkeypatch.setattr("aec.commands.repo.load_env_file", lambda: None)

        with pytest.raises(SystemExit):
            setup(path=None)


class TestCleanAgentinfoRedundancy:
    """Test advisory check for redundant rule references in AGENTINFO.md."""

    def test_warns_on_cursor_rules_reference(self, tmp_path, capsys):
        """Detects .cursor/rules references in AGENTINFO.md."""
        from aec.commands.repo import _clean_agentinfo_redundancy

        agentinfo = tmp_path / "AGENTINFO.md"
        agentinfo.write_text("# Project\n\nSee .cursor/rules/general/architecture.mdc\n")

        _clean_agentinfo_redundancy(tmp_path)

        output = capsys.readouterr().out
        assert "redundant" in output.lower() or "AGENTINFO" in output

    def test_warns_on_agent_rules_reference(self, tmp_path, capsys):
        """Detects .agent-rules references in AGENTINFO.md."""
        from aec.commands.repo import _clean_agentinfo_redundancy

        agentinfo = tmp_path / "AGENTINFO.md"
        agentinfo.write_text("# Project\n\nRead .agent-rules/testing.md\n")

        _clean_agentinfo_redundancy(tmp_path)

        output = capsys.readouterr().out
        assert "redundant" in output.lower() or "AGENTINFO" in output

    def test_no_warning_on_clean_agentinfo(self, tmp_path, capsys):
        """No warning when AGENTINFO.md has no rule references."""
        from aec.commands.repo import _clean_agentinfo_redundancy

        agentinfo = tmp_path / "AGENTINFO.md"
        agentinfo.write_text("# Project\n\n## Stack\nPython + FastAPI\n")

        _clean_agentinfo_redundancy(tmp_path)

        output = capsys.readouterr().out
        assert "redundant" not in output.lower()

    def test_no_error_when_agentinfo_missing(self, tmp_path):
        """Does nothing when AGENTINFO.md doesn't exist."""
        from aec.commands.repo import _clean_agentinfo_redundancy

        # Should not raise
        _clean_agentinfo_redundancy(tmp_path)

    def test_dry_run_mode(self, tmp_path, capsys):
        """In dry-run mode, says 'Would clean' instead of 'Manual review'."""
        from aec.commands.repo import _clean_agentinfo_redundancy

        agentinfo = tmp_path / "AGENTINFO.md"
        agentinfo.write_text("# Project\nSee .cursor/rules/foo.mdc\n")

        _clean_agentinfo_redundancy(tmp_path, dry_run=True)

        output = capsys.readouterr().out
        assert "would clean" in output.lower() or "Would clean" in output


class TestEnvLoading:
    """Test that .env file loading works in repo setup flow."""

    def test_load_env_file_sets_variables(self, tmp_path, monkeypatch):
        """load_env_file() reads .env and sets environment variables."""
        from aec.lib.config import load_env_file

        env_file = tmp_path / ".env"
        env_file.write_text("TEST_AEC_VAR=hello_world\n")

        monkeypatch.setattr("aec.lib.config.get_repo_root", lambda: tmp_path)
        # Clean up after test
        monkeypatch.delenv("TEST_AEC_VAR", raising=False)

        load_env_file()

        import os
        assert os.environ.get("TEST_AEC_VAR") == "hello_world"

    def test_load_env_file_skips_comments(self, tmp_path, monkeypatch):
        """load_env_file() ignores comment lines."""
        from aec.lib.config import load_env_file

        env_file = tmp_path / ".env"
        env_file.write_text("# comment\nTEST_AEC_COMMENT=yes\n")

        monkeypatch.setattr("aec.lib.config.get_repo_root", lambda: tmp_path)
        monkeypatch.delenv("TEST_AEC_COMMENT", raising=False)

        load_env_file()

        import os
        assert os.environ.get("TEST_AEC_COMMENT") == "yes"

    def test_load_env_file_noop_when_missing(self, tmp_path, monkeypatch):
        """load_env_file() does nothing when .env doesn't exist."""
        from aec.lib.config import load_env_file

        monkeypatch.setattr("aec.lib.config.get_repo_root", lambda: tmp_path)

        # Should not raise
        load_env_file()
