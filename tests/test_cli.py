"""Tests for aec CLI commands."""

import subprocess
import sys
from pathlib import Path

import pytest


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_help_works(self):
        """CLI should show help."""
        result = subprocess.run(
            [sys.executable, "-m", "aec", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "agents-environment-config" in result.stdout
        assert "install" in result.stdout
        assert "doctor" in result.stdout

    def test_version_works(self):
        """CLI should show version."""
        result = subprocess.run(
            [sys.executable, "-m", "aec", "version"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "aec version" in result.stdout

    def test_unknown_command_fails(self):
        """Unknown commands should fail gracefully."""
        result = subprocess.run(
            [sys.executable, "-m", "aec", "unknown-command"],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0


class TestDoctorCommand:
    """Test the doctor command."""

    def test_doctor_runs(self):
        """Doctor command should run without crashing."""
        result = subprocess.run(
            [sys.executable, "-m", "aec", "doctor"],
            capture_output=True,
            text=True,
        )

        # Doctor might find issues but shouldn't crash
        assert "AEC Health Check" in result.stdout
        assert "Platform:" in result.stdout


class TestRulesCommands:
    """Test rules subcommands."""

    def test_rules_help(self):
        """Rules subcommand should show help."""
        result = subprocess.run(
            [sys.executable, "-m", "aec", "rules", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "generate" in result.stdout
        assert "validate" in result.stdout

    def test_rules_validate_runs(self):
        """Rules validate should run."""
        result = subprocess.run(
            [sys.executable, "-m", "aec", "rules", "validate"],
            capture_output=True,
            text=True,
        )

        # Should complete (pass or fail based on state)
        assert "Validate Rule Parity" in result.stdout


class TestRepoCommands:
    """Test repo subcommands."""

    def test_repo_help(self):
        """Repo subcommand should show help."""
        result = subprocess.run(
            [sys.executable, "-m", "aec", "repo", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "setup" in result.stdout
        assert "list" in result.stdout
        assert "update" in result.stdout

    def test_repo_list_runs(self):
        """Repo list should run."""
        result = subprocess.run(
            [sys.executable, "-m", "aec", "repo", "list"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Tracked Repositories" in result.stdout


class TestAgentToolsCommands:
    """Test agent-tools subcommands."""

    def test_agent_tools_help(self):
        """Agent-tools subcommand should show help."""
        result = subprocess.run(
            [sys.executable, "-m", "aec", "agent-tools", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "setup" in result.stdout
        assert "migrate" in result.stdout
        assert "rollback" in result.stdout
