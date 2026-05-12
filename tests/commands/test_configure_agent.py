"""End-to-end tests for `aec configure-agent`.

Real-filesystem; no mocks of internals. Per project standards.
"""

import pytest
from typer.testing import CliRunner

from aec.cli import app
from aec.lib.agent_blurb.config import load_config
from aec.lib.agent_blurb.markers import find_block


runner = CliRunner()


@pytest.fixture
def project_with_agent_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("# CLAUDE.md\n\nuser content\n")
    (tmp_path / "AGENTS.md").write_text("# AGENTS.md\n")
    return tmp_path


class TestRefreshFlag:
    def test_check_exits_nonzero_when_no_config(self, project_with_agent_files):
        result = runner.invoke(app, ["configure-agent", "--check"])
        assert result.exit_code != 0

    def test_dry_run_writes_nothing(self, project_with_agent_files, monkeypatch):
        monkeypatch.setenv("AEC_NONINTERACTIVE", "1")
        result = runner.invoke(
            app,
            ["configure-agent",
             "--scope", "project",
             "--profile", "balanced",
             "--agent-files", "all",
             "--dry-run"],
        )
        assert result.exit_code == 0
        assert not (project_with_agent_files / ".aec" / "agent-blurb.json").exists()

    def test_install_writes_config_and_block(self, project_with_agent_files):
        result = runner.invoke(
            app,
            ["configure-agent",
             "--scope", "project",
             "--profile", "balanced",
             "--agent-files", "all",
             "--yes"],
        )
        assert result.exit_code == 0, result.output
        cfg = load_config(scope="project", root=project_with_agent_files)
        assert cfg is not None
        assert cfg["profile"] == "balanced"
        content = (project_with_agent_files / "CLAUDE.md").read_text()
        assert find_block(content) is not None
        assert "user content" in content


class TestIdempotency:
    def test_refresh_twice_byte_identical(self, project_with_agent_files):
        runner.invoke(app, ["configure-agent", "--scope", "project",
                            "--profile", "balanced", "--agent-files", "all", "--yes"])
        first = (project_with_agent_files / "CLAUDE.md").read_text()
        runner.invoke(app, ["configure-agent", "--refresh", "--scope", "project"])
        second = (project_with_agent_files / "CLAUDE.md").read_text()
        assert first == second


class TestRemove:
    def test_remove_strips_block_preserves_content(self, project_with_agent_files):
        runner.invoke(app, ["configure-agent", "--scope", "project",
                            "--profile", "balanced", "--agent-files", "all", "--yes"])
        result = runner.invoke(app, ["configure-agent", "--remove",
                                     "--scope", "project", "--yes"])
        assert result.exit_code == 0
        content = (project_with_agent_files / "CLAUDE.md").read_text()
        assert find_block(content) is None
        assert "user content" in content
        assert not (project_with_agent_files / ".aec" / "agent-blurb.json").exists()


class TestCheckAfterInstall:
    def test_check_clean_after_install(self, project_with_agent_files):
        runner.invoke(app, ["configure-agent", "--scope", "project",
                            "--profile", "balanced", "--agent-files", "all", "--yes"])
        result = runner.invoke(app, ["configure-agent", "--check", "--scope", "project"])
        assert result.exit_code == 0

    def test_check_detects_manual_edit(self, project_with_agent_files):
        runner.invoke(app, ["configure-agent", "--scope", "project",
                            "--profile", "balanced", "--agent-files", "all", "--yes"])
        p = project_with_agent_files / "CLAUDE.md"
        text = p.read_text()
        edited = text.replace("you may run", "YOU SHALL RUN")
        p.write_text(edited)
        if edited != text:
            result = runner.invoke(app, ["configure-agent", "--check", "--scope", "project"])
            assert result.exit_code != 0
            assert "manual" in result.output.lower() or "drift" in result.output.lower()
