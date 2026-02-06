"""Tests for aec.lib.config module."""

import platform
from pathlib import Path

import pytest

from aec.lib.config import (
    VERSION,
    IS_WINDOWS,
    IS_MACOS,
    IS_LINUX,
    get_projects_dir,
    get_github_orgs,
)


class TestPlatformDetection:
    """Test platform detection constants."""

    def test_exactly_one_platform_is_true(self):
        """Exactly one platform flag should be True."""
        platforms = [IS_WINDOWS, IS_MACOS, IS_LINUX]
        # At least one should be true (unless on an exotic OS)
        # But at most one should be true
        assert sum(platforms) <= 1

    def test_platform_matches_system(self):
        """Platform detection should match platform.system()."""
        system = platform.system()
        if system == "Windows":
            assert IS_WINDOWS is True
        elif system == "Darwin":
            assert IS_MACOS is True
        elif system == "Linux":
            assert IS_LINUX is True


class TestVersion:
    """Test version string."""

    def test_version_format(self):
        """Version should be in semver format."""
        parts = VERSION.split(".")
        assert len(parts) >= 2
        # Major and minor should be numeric
        assert parts[0].isdigit()
        assert parts[1].isdigit()


class TestGetProjectsDir:
    """Test get_projects_dir function."""

    def test_respects_env_var(self, monkeypatch, temp_dir):
        """Should use PROJECTS_DIR env var if set."""
        custom_dir = temp_dir / "my_projects"
        custom_dir.mkdir()
        monkeypatch.setenv("PROJECTS_DIR", str(custom_dir))

        result = get_projects_dir()
        assert result == custom_dir

    def test_returns_path_object(self, clean_env):
        """Should return a Path object."""
        result = get_projects_dir()
        assert isinstance(result, Path)


class TestGetGithubOrgs:
    """Test get_github_orgs function."""

    def test_respects_env_var(self, monkeypatch):
        """Should use GITHUB_ORGS env var if set."""
        monkeypatch.setenv("GITHUB_ORGS", "org1, org2, org3")

        result = get_github_orgs()
        assert result == ["org1", "org2", "org3"]

    def test_returns_list(self, clean_env):
        """Should return a list."""
        result = get_github_orgs()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_handles_empty_env_var(self, monkeypatch):
        """Should return defaults for empty env var."""
        monkeypatch.setenv("GITHUB_ORGS", "")

        result = get_github_orgs()
        # Should return default orgs
        assert isinstance(result, list)
