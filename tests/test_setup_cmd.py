"""Tests for aec setup command."""

import pytest
from pathlib import Path


@pytest.fixture
def setup_env(temp_dir, monkeypatch):
    """Set up environment for setup command tests."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)
    aec_home = temp_dir / ".agents-environment-config"

    # Patch AEC_HOME and AEC_SETUP_LOG in the modules that use them
    setup_log = aec_home / "setup-repo-locations.txt"
    readme = aec_home / "README.md"
    monkeypatch.setattr("aec.lib.tracking.AEC_HOME", aec_home)
    monkeypatch.setattr("aec.lib.tracking.AEC_SETUP_LOG", setup_log)
    monkeypatch.setattr("aec.lib.tracking.AEC_README", readme)
    monkeypatch.setattr("aec.commands.setup.AEC_HOME", aec_home)

    return {"home": temp_dir, "aec_home": aec_home, "setup_log": setup_log}


class TestSetup:
    def test_functions_importable(self):
        from aec.commands.setup import run_setup, run_setup_path, run_setup_all
        assert callable(run_setup)
        assert callable(run_setup_path)
        assert callable(run_setup_all)

    def test_setup_path_errors_on_nonexistent(self, setup_env):
        from aec.commands.setup import run_setup_path
        with pytest.raises(SystemExit):
            run_setup_path("/nonexistent/path/12345")

    def test_setup_path_already_tracked(self, setup_env, capsys):
        """Calling run_setup_path on an already-tracked repo prints info message."""
        from aec.commands.setup import run_setup_path
        from aec.lib.tracking import log_setup, is_logged

        project = setup_env["home"] / "projects" / "test-app"
        project.mkdir(parents=True)
        (project / ".git").mkdir()

        setup_env["aec_home"].mkdir(parents=True)
        setup_env["setup_log"].write_text("")

        # Pre-track the project
        log_setup(project)
        assert is_logged(project)

        # Calling setup_path should report "already tracked" and return
        run_setup_path(str(project))
        captured = capsys.readouterr()
        assert "Already tracked" in captured.out

    def test_setup_no_args_not_installed_delegates_to_install(
        self, setup_env, monkeypatch
    ):
        """When AEC_HOME doesn't exist, run_setup delegates to install()."""
        install_called = []

        def fake_install(dry_run=False):
            install_called.append(dry_run)

        # Patch install.install at the source so the lazy import picks it up
        monkeypatch.setattr("aec.commands.install.install", fake_install)

        # AEC_HOME does not exist yet
        assert not setup_env["aec_home"].exists()

        from aec.commands.setup import run_setup
        run_setup()
        assert len(install_called) == 1
        assert install_called[0] is False

    def test_setup_no_args_installed_shows_status(self, setup_env, capsys):
        """When AEC_HOME exists and not in a repo, shows status."""
        setup_env["aec_home"].mkdir(parents=True)
        setup_env["setup_log"].write_text("")

        from aec.commands.setup import run_setup
        # Monkeypatch find_tracked_repo to return None
        import aec.commands.setup as setup_mod
        setup_env["home"]  # not in a git repo

        # Patch find_tracked_repo to return None (we're not in a tracked repo)
        from unittest.mock import patch
        with patch.object(setup_mod, "find_tracked_repo", return_value=None):
            # And we're not in a git directory
            with patch.object(Path, "cwd", return_value=setup_env["home"]):
                run_setup()

        captured = capsys.readouterr()
        assert "AEC is installed" in captured.out
        assert "aec doctor" in captured.out

    def test_setup_path_dry_run(self, setup_env, capsys):
        """Dry run reports what would happen without delegating to repo.setup."""
        project = setup_env["home"] / "projects" / "dry-app"
        project.mkdir(parents=True)
        (project / ".git").mkdir()

        setup_env["aec_home"].mkdir(parents=True)
        setup_env["setup_log"].write_text("")

        from aec.commands.setup import run_setup_path
        run_setup_path(str(project), dry_run=True)

        captured = capsys.readouterr()
        assert "Would track" in captured.out
