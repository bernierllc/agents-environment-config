# tests/test_cli_v2.py
"""Tests for the new flat CLI command structure."""

import subprocess
import sys

import pytest


class TestCLIHelp:
    def test_top_level_help_shows_flat_commands(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "--help"],
            capture_output=True, text=True,
        )
        output = result.stdout
        assert "update" in output
        assert "upgrade" in output
        assert "install" in output
        assert "uninstall" in output
        assert "list" in output
        assert "search" in output
        assert "outdated" in output
        assert "info" in output
        assert "setup" in output
        assert "untrack" in output
        assert "config" in output
        assert "generate" in output
        assert "validate" in output
        assert "doctor" in output

    def test_top_level_help_shows_version(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "--help"],
            capture_output=True, text=True,
        )
        assert "version" in result.stdout

    def test_top_level_help_shows_prune(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "--help"],
            capture_output=True, text=True,
        )
        assert "prune" in result.stdout

    def test_top_level_help_shows_discover(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "--help"],
            capture_output=True, text=True,
        )
        assert "discover" in result.stdout


class TestDeprecatedGroupsStillRegistered:
    """Deprecated command groups should still appear in help."""

    def test_repo_group_still_accessible(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "repo", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_skills_group_still_accessible(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "skills", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_rules_group_still_accessible(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "rules", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_files_group_still_accessible(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "files", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_preferences_group_still_accessible(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "preferences", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_agent_tools_group_still_accessible(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "agent-tools", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0


class TestNewCommandHelp:
    """New flat commands should show their own help."""

    def test_config_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "config", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "list" in result.stdout
        assert "set" in result.stdout
        assert "reset" in result.stdout

    def test_generate_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "generate", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "rules" in result.stdout
        assert "files" in result.stdout
