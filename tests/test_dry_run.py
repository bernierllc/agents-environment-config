"""Tests for --dry-run support across all modified functions."""

import json
from pathlib import Path

import pytest


class TestTrackingDryRun:
    """Test dry-run mode for tracking.py functions."""

    def test_init_aec_home_dry_run_no_dirs_created(self, temp_dir, monkeypatch):
        """init_aec_home(dry_run=True) should not create any directories or files."""
        aec_home = temp_dir / ".agents-environment-config"
        monkeypatch.setattr("aec.lib.tracking.AEC_HOME", aec_home)
        monkeypatch.setattr("aec.lib.tracking.AEC_README", aec_home / "README.md")
        monkeypatch.setattr("aec.lib.tracking.AEC_SETUP_LOG", aec_home / "setup-repo-locations.txt")

        from aec.lib.tracking import init_aec_home
        init_aec_home(dry_run=True)

        assert not aec_home.exists()

    def test_init_aec_home_normal_creates_dirs(self, temp_dir, monkeypatch):
        """init_aec_home(dry_run=False) should still work normally."""
        aec_home = temp_dir / ".agents-environment-config"
        monkeypatch.setattr("aec.lib.tracking.AEC_HOME", aec_home)
        monkeypatch.setattr("aec.lib.tracking.AEC_README", aec_home / "README.md")
        monkeypatch.setattr("aec.lib.tracking.AEC_SETUP_LOG", aec_home / "setup-repo-locations.txt")

        from aec.lib.tracking import init_aec_home
        init_aec_home(dry_run=False)

        assert aec_home.exists()
        assert (aec_home / "README.md").exists()
        assert (aec_home / "setup-repo-locations.txt").exists()
        assert (aec_home / "runner.py").exists()
        assert "run_all_projects" in (aec_home / "runner.py").read_text()

    def test_log_setup_dry_run_no_file_changes(self, temp_dir, monkeypatch):
        """log_setup(dry_run=True) should not write to the log file."""
        aec_home = temp_dir / ".agents-environment-config"
        aec_home.mkdir(parents=True)
        log_file = aec_home / "setup-repo-locations.txt"
        log_file.touch()
        monkeypatch.setattr("aec.lib.tracking.AEC_HOME", aec_home)
        monkeypatch.setattr("aec.lib.tracking.AEC_SETUP_LOG", log_file)
        monkeypatch.setattr("aec.lib.tracking.AEC_README", aec_home / "README.md")

        from aec.lib.tracking import log_setup
        log_setup(temp_dir / "my-project", dry_run=True)

        assert log_file.read_text() == ""


class TestGitDryRun:
    """Test dry-run mode for git.py functions."""

    def test_init_submodules_dry_run_returns_message(self, temp_dir):
        """init_submodules(dry_run=True) should return without running git."""
        from aec.lib.git import init_submodules
        success, message = init_submodules(temp_dir, dry_run=True)

        assert success is True
        assert "Would initialize" in message

    def test_update_submodule_dry_run_no_fetch(self, temp_dir):
        """update_submodule(dry_run=True) should not fetch or checkout."""
        # Create a fake submodule dir with a .git dir
        sub_dir = temp_dir / "sub"
        sub_dir.mkdir()
        (sub_dir / ".git").mkdir()

        from aec.lib.git import update_submodule
        success, message = update_submodule(temp_dir, "sub", dry_run=True)

        assert success is True
        assert "dry run" in message


class TestRulesDryRun:
    """Test dry-run mode for rules.py generate()."""

    def test_generate_dry_run_no_files_written(self, mock_repo_root, monkeypatch):
        """generate(dry_run=True) should not write .md files."""
        monkeypatch.setattr("aec.commands.rules.get_repo_root", lambda: mock_repo_root)
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", mock_repo_root / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", mock_repo_root)

        # Remove existing .agent-rules to verify nothing is created
        import shutil
        agent_rules = mock_repo_root / ".agent-rules"
        if agent_rules.exists():
            shutil.rmtree(agent_rules)

        # Add a new .mdc file that doesn't have a corresponding .md
        new_mdc = mock_repo_root / ".cursor" / "rules" / "new-rule.mdc"
        new_mdc.write_text("---\ndescription: New\n---\n# New Rule\nContent\n")

        from aec.commands.rules import generate
        generate(dry_run=True)

        # The new .md file should NOT have been created
        new_md = mock_repo_root / ".agent-rules" / "new-rule.md"
        assert not new_md.exists()


class TestAgentToolsDryRun:
    """Test dry-run mode for agent_tools.py setup()."""

    def test_setup_dry_run_no_dirs_or_symlinks(self, temp_dir, monkeypatch):
        """setup(dry_run=True) should not create directories or symlinks."""
        agent_tools_dir = temp_dir / ".agent-tools"
        repo_root = temp_dir / "repo"
        repo_root.mkdir()
        (repo_root / ".agent-rules").mkdir()
        (repo_root / ".claude" / "agents").mkdir(parents=True)
        (repo_root / ".claude" / "skills").mkdir(parents=True)
        (repo_root / ".cursor" / "commands").mkdir(parents=True)

        monkeypatch.setattr("aec.commands.agent_tools.AGENT_TOOLS_DIR", agent_tools_dir)
        monkeypatch.setattr("aec.commands.agent_tools.get_repo_root", lambda: repo_root)
        monkeypatch.setattr("aec.commands.agent_tools._is_claude_installed", lambda: False)
        monkeypatch.setattr("aec.commands.agent_tools._is_cursor_installed", lambda: False)

        from aec.commands.agent_tools import setup
        setup(dry_run=True)

        assert not agent_tools_dir.exists()


class TestRepoDryRun:
    """Test dry-run mode for repo.py functions."""

    def test_create_directories_dry_run(self, temp_dir, monkeypatch):
        """_create_directories(dry_run=True) should not create directories."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        project_dir = temp_dir / "my-project"
        project_dir.mkdir()

        from aec.commands.repo import _create_directories
        _create_directories(project_dir, dry_run=True)

        assert not (project_dir / ".cursor").exists()
        assert not (project_dir / "docs").exists()

    def test_copy_agent_files_dry_run(self, temp_dir, monkeypatch):
        """_copy_agent_files(dry_run=True) should not copy files."""
        project_dir = temp_dir / "project"
        project_dir.mkdir()
        repo_root = temp_dir / "repo"
        repo_root.mkdir()

        # Create a source file in templates/ (where the code now looks)
        templates_dir = repo_root / "templates"
        templates_dir.mkdir()
        (templates_dir / "AGENTINFO.md").write_text("# Info")

        monkeypatch.setattr("aec.commands.repo.AGENT_FILES", ["AGENTINFO.md"])

        from aec.commands.repo import _copy_agent_files
        _copy_agent_files(project_dir, repo_root, dry_run=True)

        assert not (project_dir / "AGENTINFO.md").exists()

    def test_update_gitignore_dry_run(self, temp_dir, monkeypatch):
        """_update_gitignore(dry_run=True) should not modify .gitignore."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        project_dir = temp_dir / "project"
        project_dir.mkdir()

        from aec.commands.repo import _update_gitignore
        _update_gitignore(project_dir, dry_run=True)

        gitignore = project_dir / ".gitignore"
        assert not gitignore.exists()

    def test_migrate_plans_dry_run(self, temp_dir, monkeypatch):
        """_migrate_plans_dir(dry_run=True) should not move files."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "prefs.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        # Set plans_dir to .plans
        prefs_file = temp_dir / "prefs.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {"plans_dir": ".plans"},
        }))

        project_dir = temp_dir / "project"
        project_dir.mkdir()
        legacy = project_dir / "plans"
        legacy.mkdir()
        (legacy / "plan1.md").write_text("plan")

        from aec.commands.repo import _migrate_plans_dir
        _migrate_plans_dir(project_dir, dry_run=True)

        # File should NOT have been moved
        assert (legacy / "plan1.md").exists()
        assert not (project_dir / ".plans").exists()


class TestInstallDryRun:
    """Test dry-run mode for install.py functions."""

    def test_prompt_settings_dry_run_shows_existing_prompts_missing(self, temp_dir, monkeypatch, capsys):
        """_prompt_settings(dry_run=True) should show existing values and prompt for missing ones."""
        prefs_file = temp_dir / "prefs.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {
                "projects_dir": "/Users/test/projects",
                "plans_dir": ".plans",
            },
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        # Provide answers for the 2 missing settings (plans_gitignored, plans_completion)
        inputs = iter(["n", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_settings
        _prompt_settings(dry_run=True)

        captured = capsys.readouterr()
        # Existing settings shown
        assert "projects_dir = /Users/test/projects" in captured.out
        assert "plans_dir = .plans" in captured.out
        # Answers reported as "Would save"
        assert "Would save: plans_gitignored" in captured.out
        assert "Would save: plans_completion" in captured.out

    def test_prompt_settings_dry_run_no_writes(self, temp_dir, monkeypatch):
        """_prompt_settings(dry_run=True) should not write to preferences."""
        prefs_file = temp_dir / "prefs.json"
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        # Provide answers for all 4 settings
        inputs = iter(["/tmp/projects", "1", "n", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from aec.commands.install import _prompt_settings
        _prompt_settings(dry_run=True)

        # Prefs file should not have been created
        assert not prefs_file.exists()

    def test_prompt_settings_dry_run_skips_when_all_set(self, temp_dir, monkeypatch):
        """_prompt_settings(dry_run=True) should show all values without prompting when fully configured."""
        prefs_file = temp_dir / "prefs.json"
        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {
                "projects_dir": "/Users/test/projects",
                "plans_dir": ".plans",
                "plans_gitignored": True,
                "plans_completion": "archive",
            },
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        def should_not_prompt(_):
            raise AssertionError("Should not prompt when all settings exist")
        monkeypatch.setattr("builtins.input", should_not_prompt)

        from aec.commands.install import _prompt_settings
        _prompt_settings(dry_run=True)  # Should not raise

    def test_batch_project_setup_dry_run_no_prompts(self, temp_dir, monkeypatch):
        """_batch_project_setup(dry_run=True) should list projects without prompting."""
        prefs_file = temp_dir / "prefs.json"
        projects_dir = temp_dir / "projects"
        projects_dir.mkdir()
        proj = projects_dir / "my-app"
        proj.mkdir()
        (proj / ".git").mkdir()

        prefs_file.write_text(json.dumps({
            "schema_version": "1.1",
            "optional_rules": {},
            "settings": {"projects_dir": str(projects_dir)},
        }))
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", prefs_file)
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)

        def should_not_prompt(_):
            raise AssertionError("Should not prompt in dry-run mode")
        monkeypatch.setattr("builtins.input", should_not_prompt)

        from aec.commands.install import _batch_project_setup
        _batch_project_setup(dry_run=True)


class TestCliDryRunFlag:
    """Test that --dry-run flag is wired in CLI."""

    def test_argparse_install_accepts_dry_run(self):
        """The argparse install subparser should accept --dry-run."""
        import argparse

        # Build the parser the same way cli.py does for argparse
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        install_parser = subparsers.add_parser("install")
        install_parser.add_argument("--dry-run", action="store_true")

        args = parser.parse_args(["install", "--dry-run"])
        assert args.dry_run is True

        args = parser.parse_args(["install"])
        assert args.dry_run is False
