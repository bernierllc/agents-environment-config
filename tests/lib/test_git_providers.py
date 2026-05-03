"""Tests for aec.lib.git_providers registry and detection functions."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest


class TestGitProvidersRegistry:
    def test_github_entry_exists(self):
        from aec.lib.git_providers import GIT_PROVIDERS
        assert "github" in GIT_PROVIDERS

    def test_each_provider_has_required_keys(self):
        from aec.lib.git_providers import GIT_PROVIDERS
        required = {"display_name", "detect_files", "detect_commands", "detect_env_vars", "essentials"}
        for key, provider in GIT_PROVIDERS.items():
            for field in required:
                assert field in provider, f"{key} missing {field}"

    def test_each_essential_has_required_keys(self):
        from aec.lib.git_providers import GIT_PROVIDERS
        for pkey, provider in GIT_PROVIDERS.items():
            for ekey, essential in provider["essentials"].items():
                assert "display" in essential, f"{pkey}.{ekey} missing display"
                assert "check" in essential, f"{pkey}.{ekey} missing check"
                assert "template" in essential, f"{pkey}.{ekey} missing template"
                assert callable(essential["check"]), f"{pkey}.{ekey} check must be callable"

    def test_all_non_none_template_paths_exist(self):
        from aec.lib.git_providers import GIT_PROVIDERS
        templates_dir = Path(__file__).parent.parent.parent / "aec" / "templates" / "git"
        missing = []
        for pkey, provider in GIT_PROVIDERS.items():
            for ekey, essential in provider["essentials"].items():
                tpl = essential["template"]
                if tpl is not None:
                    path = templates_dir / tpl
                    if not path.exists():
                        missing.append(f"{pkey}.{ekey}: {tpl}")
        assert not missing, f"Missing template files: {missing}"

    def test_github_has_nine_essentials(self):
        from aec.lib.git_providers import GIT_PROVIDERS
        assert len(GIT_PROVIDERS["github"]["essentials"]) == 9


class TestDetectGitProvider:
    def test_returns_none_when_no_git_dir(self, tmp_path):
        from aec.lib.git_providers import detect_git_provider
        assert detect_git_provider(tmp_path) is None

    def test_returns_unknown_when_git_but_no_signals(self, tmp_path):
        (tmp_path / ".git").mkdir()
        from aec.lib.git_providers import detect_git_provider
        with patch("shutil.which", return_value=None):
            with patch.dict(os.environ, {}, clear=True):
                result = detect_git_provider(tmp_path)
        assert result == "unknown"

    def test_detects_github_via_dot_github_dir(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".github").mkdir()
        from aec.lib.git_providers import detect_git_provider
        with patch("shutil.which", return_value=None):
            with patch.dict(os.environ, {}, clear=True):
                result = detect_git_provider(tmp_path)
        assert result == "github"

    def test_detects_github_via_gh_command(self, tmp_path):
        (tmp_path / ".git").mkdir()
        from aec.lib.git_providers import detect_git_provider
        with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/gh" if cmd == "gh" else None):
            with patch.dict(os.environ, {}, clear=True):
                result = detect_git_provider(tmp_path)
        assert result == "github"

    def test_detects_github_via_env_var(self, tmp_path):
        (tmp_path / ".git").mkdir()
        from aec.lib.git_providers import detect_git_provider
        with patch("shutil.which", return_value=None):
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test"}, clear=False):
                result = detect_git_provider(tmp_path)
        assert result == "github"


class TestScanGitEssentials:
    def test_all_missing_when_empty_dir(self, tmp_path):
        (tmp_path / ".git").mkdir()
        from aec.lib.git_providers import scan_git_essentials
        result = scan_git_essentials(tmp_path, "github")
        assert all(v == "missing" for v in result.values())

    def test_gitignore_found_when_exists(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".gitignore").write_text("node_modules/")
        from aec.lib.git_providers import scan_git_essentials
        result = scan_git_essentials(tmp_path, "github")
        assert result[".gitignore"] == "found"
        assert result["README.md"] == "missing"

    def test_returns_dict_with_all_nine_keys(self, tmp_path):
        (tmp_path / ".git").mkdir()
        from aec.lib.git_providers import scan_git_essentials
        result = scan_git_essentials(tmp_path, "github")
        assert len(result) == 9
        assert all(v in ("found", "missing") for v in result.values())
