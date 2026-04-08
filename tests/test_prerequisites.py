"""Tests for aec.lib.prerequisites module."""

import subprocess

import pytest


class TestPrerequisiteChecksRegistry:
    """Test the PREREQUISITE_CHECKS registry is well-formed."""

    def test_registry_has_expected_entries(self):
        """Registry should contain all expected prerequisites."""
        from aec.lib.prerequisites import PREREQUISITE_CHECKS

        expected = {
            "docker", "node", "npm", "python", "pip",
            "cargo", "go", "ruby", "bundle",
        }
        assert set(PREREQUISITE_CHECKS.keys()) == expected

    def test_each_entry_has_required_keys(self):
        """Each entry must have display_name and check keys."""
        from aec.lib.prerequisites import PREREQUISITE_CHECKS

        for key, entry in PREREQUISITE_CHECKS.items():
            assert "display_name" in entry, f"{key} missing display_name"
            assert "check" in entry, f"{key} missing check"

    def test_check_values_are_callable(self):
        """Each check value must be callable."""
        from aec.lib.prerequisites import PREREQUISITE_CHECKS

        for key, entry in PREREQUISITE_CHECKS.items():
            assert callable(entry["check"]), f"{key} check is not callable"


class TestCheckCommand:
    """Test _check_command function."""

    def test_returns_true_for_known_command(self):
        """Should return True for a command known to exist (sh)."""
        from aec.lib.prerequisites import _check_command

        available, detail = _check_command("sh")
        assert available is True
        assert "/" in detail  # should be an absolute path

    def test_returns_false_for_nonexistent_command(self):
        """Should return False for a command that does not exist."""
        from aec.lib.prerequisites import _check_command

        available, detail = _check_command("nonexistent_tool_xyz_999")
        assert available is False
        assert detail == "not found on PATH"


class TestCheckDocker:
    """Test _check_docker function."""

    def test_docker_command_not_found(self, monkeypatch):
        """Should report docker command not found when which returns None."""
        import shutil

        monkeypatch.setattr(shutil, "which", lambda name: None)

        from aec.lib.prerequisites import _check_docker

        available, detail = _check_docker()
        assert available is False
        assert detail == "docker command not found"

    def test_docker_daemon_not_running(self, monkeypatch):
        """Should report Docker not running when docker info fails."""
        import shutil

        monkeypatch.setattr(
            shutil, "which", lambda name: "/usr/bin/docker"
        )
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args=args, returncode=1
            ),
        )

        from aec.lib.prerequisites import _check_docker

        available, detail = _check_docker()
        assert available is False
        assert detail == "Docker not running"

    def test_docker_running(self, monkeypatch):
        """Should report Docker running when docker info succeeds."""
        import shutil

        monkeypatch.setattr(
            shutil, "which", lambda name: "/usr/bin/docker"
        )
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, **kwargs: subprocess.CompletedProcess(
                args=args, returncode=0
            ),
        )

        from aec.lib.prerequisites import _check_docker

        available, detail = _check_docker()
        assert available is True
        assert detail == "Docker running"


class TestCheckPrerequisite:
    """Test check_prerequisite function."""

    def test_known_prerequisite(self):
        """Should use registry check for a known prerequisite name."""
        from aec.lib.prerequisites import check_prerequisite

        available, detail = check_prerequisite("python")
        # python3 or python should be available in test environment
        assert isinstance(available, bool)
        assert isinstance(detail, str)

    def test_unknown_name_falls_back_to_command_check(self):
        """Unknown names should fall back to _check_command."""
        from aec.lib.prerequisites import check_prerequisite

        available, detail = check_prerequisite("nonexistent_tool_xyz_999")
        assert available is False
        assert detail == "not found on PATH"

    def test_unknown_name_found_as_command(self):
        """Unknown name that exists as a command should return True."""
        from aec.lib.prerequisites import check_prerequisite

        available, detail = check_prerequisite("sh")
        assert available is True
        assert "/" in detail


class TestCheckPrerequisites:
    """Test check_prerequisites function."""

    def test_returns_correct_count(self):
        """Should return one result per input name."""
        from aec.lib.prerequisites import check_prerequisites

        names = ["sh", "nonexistent_tool_xyz_999", "python"]
        results = check_prerequisites(names)
        assert len(results) == 3

    def test_preserves_input_order(self):
        """Result order should match input order."""
        from aec.lib.prerequisites import check_prerequisites

        names = ["nonexistent_tool_xyz_999", "sh", "python"]
        results = check_prerequisites(names)
        assert results[0][0] == "nonexistent_tool_xyz_999"
        assert results[1][0] == "sh"
        assert results[2][0] == "python"

    def test_result_tuple_structure(self):
        """Each result should be a (name, available, detail) tuple."""
        from aec.lib.prerequisites import check_prerequisites

        results = check_prerequisites(["sh"])
        name, available, detail = results[0]
        assert name == "sh"
        assert isinstance(available, bool)
        assert isinstance(detail, str)
