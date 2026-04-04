"""Tests for aec untrack command."""

import pytest
from pathlib import Path


@pytest.fixture
def untrack_env(temp_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()
    project = temp_dir / "projects" / "my-app"
    project.mkdir(parents=True)
    log = aec_home / "setup-repo-locations.txt"
    log.write_text(f"2026-04-04T00:00:00Z|2.5.4|{project.resolve()}\n")
    return {"project": project, "log": log}


class TestUntrack:
    def test_removes_from_tracking(self, untrack_env):
        from aec.commands.untrack import run_untrack
        from aec.lib.tracking import is_logged

        assert is_logged(untrack_env["project"])
        run_untrack(str(untrack_env["project"]), yes=True)
        assert not is_logged(untrack_env["project"])

    def test_warning_for_untracked_path(self, untrack_env, capsys):
        from aec.commands.untrack import run_untrack

        run_untrack("/nonexistent/path", yes=True)
        output = capsys.readouterr().out
        assert "not tracked" in output.lower()
