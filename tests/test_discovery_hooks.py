"""Tests for aec.lib.discovery_hooks — Quick-scan notification."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from aec.lib.discovery_hooks import (
    quick_scan_notification,
    _normalize_name,
    _scan_local_items,
    _is_dismissed,
    _get_installed_names,
)
from aec.lib.scope import Scope


# ---------------------------------------------------------------------------
# Unit tests for _normalize_name
# ---------------------------------------------------------------------------

class TestNormalizeName:
    def test_strips_md_extension(self):
        assert _normalize_name("backend-architect.md") == "backend-architect"

    def test_strips_engineering_prefix(self):
        assert _normalize_name("engineering-backend-architect.md") == "backend-architect"

    def test_strips_custom_prefix(self):
        assert _normalize_name("custom-reviewer.md") == "reviewer"

    def test_strips_aec_prefix(self):
        assert _normalize_name("aec-helper.md") == "helper"

    def test_lowercases(self):
        assert _normalize_name("My-Agent.MD") == "my-agent"

    def test_directory_name(self):
        assert _normalize_name("webapp-testing") == "webapp-testing"

    def test_no_prefix_no_extension(self):
        assert _normalize_name("simple") == "simple"


# ---------------------------------------------------------------------------
# Unit tests for _scan_local_items
# ---------------------------------------------------------------------------

class TestScanLocalItems:
    def test_lists_files_and_dirs(self, tmp_path):
        (tmp_path / "agent-a.md").touch()
        (tmp_path / "skill-b").mkdir()
        result = _scan_local_items(tmp_path)
        assert sorted(result) == ["agent-a.md", "skill-b"]

    def test_skips_hidden_files(self, tmp_path):
        (tmp_path / ".hidden").touch()
        (tmp_path / "visible.md").touch()
        result = _scan_local_items(tmp_path)
        assert result == ["visible.md"]

    def test_returns_empty_for_missing_dir(self, tmp_path):
        result = _scan_local_items(tmp_path / "nonexistent")
        assert result == []


# ---------------------------------------------------------------------------
# Unit tests for _is_dismissed
# ---------------------------------------------------------------------------

class TestIsDismissed:
    def test_returns_false_when_file_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert _is_dismissed("some-agent.md", "agents") is False

    def test_returns_true_when_item_dismissed(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        aec_home = tmp_path / ".agents-environment-config"
        aec_home.mkdir(parents=True)
        dismissed = {
            "schemaVersion": 1,
            "items": {
                "old-agent.md": {
                    "dismissedAt": "2026-04-10T18:00:00Z",
                    "matchedCatalogItem": "engineering-code-reviewer",
                }
            },
        }
        (aec_home / "dismissed-agents.json").write_text(json.dumps(dismissed))
        assert _is_dismissed("old-agent.md", "agents") is True

    def test_returns_false_when_item_not_in_dismissed(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        aec_home = tmp_path / ".agents-environment-config"
        aec_home.mkdir(parents=True)
        dismissed = {"schemaVersion": 1, "items": {}}
        (aec_home / "dismissed-agents.json").write_text(json.dumps(dismissed))
        assert _is_dismissed("new-agent.md", "agents") is False

    def test_returns_false_on_corrupt_json(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        aec_home = tmp_path / ".agents-environment-config"
        aec_home.mkdir(parents=True)
        (aec_home / "dismissed-agents.json").write_text("not json{{{")
        assert _is_dismissed("anything.md", "agents") is False


# ---------------------------------------------------------------------------
# Unit tests for _get_installed_names
# ---------------------------------------------------------------------------

class TestGetInstalledNames:
    def test_returns_empty_when_no_manifest(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert _get_installed_names("agents") == set()

    def test_returns_installed_names(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        aec_home = tmp_path / ".agents-environment-config"
        aec_home.mkdir(parents=True)
        manifest = {
            "manifestVersion": 2,
            "global": {
                "skills": {"my-skill": {"version": "1.0.0"}},
                "agents": {"my-agent": {"version": "1.0.0"}},
                "rules": {},
            },
        }
        (aec_home / "installed-manifest.json").write_text(json.dumps(manifest))
        assert _get_installed_names("skills") == {"my-skill"}
        assert _get_installed_names("agents") == {"my-agent"}
        assert _get_installed_names("rules") == set()

    def test_returns_empty_on_corrupt_manifest(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        aec_home = tmp_path / ".agents-environment-config"
        aec_home.mkdir(parents=True)
        (aec_home / "installed-manifest.json").write_text("broken{{{")
        assert _get_installed_names("agents") == set()


# ---------------------------------------------------------------------------
# Integration tests for quick_scan_notification
# ---------------------------------------------------------------------------

@pytest.fixture
def scan_env(tmp_path, monkeypatch):
    """Set up environment for quick_scan_notification tests."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Create local agents and skills dirs with untracked items
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)

    # AEC home with empty manifest
    aec_home = tmp_path / ".agents-environment-config"
    aec_home.mkdir(parents=True)
    manifest = {
        "manifestVersion": 2,
        "global": {"skills": {}, "agents": {}, "rules": {}},
        "repos": {},
    }
    (aec_home / "installed-manifest.json").write_text(json.dumps(manifest))

    return {
        "tmp_path": tmp_path,
        "agents_dir": agents_dir,
        "skills_dir": skills_dir,
        "aec_home": aec_home,
    }


def _mock_catalog():
    """Return a mock catalog with known items."""
    return {
        "backend-architect": {"version": "1.0.0", "path": "backend-architect.md"},
        "code-reviewer": {"version": "1.0.0", "path": "code-reviewer.md"},
    }


class TestQuickScanNotification:
    def test_shows_notification_when_matches_found(self, scan_env, capsys):
        """Notification is printed when untracked items match catalog names."""
        # Create a local agent that matches catalog after normalization
        (scan_env["agents_dir"] / "engineering-backend-architect.md").touch()

        with patch("aec.lib.discovery_hooks.get_source_dirs") as mock_dirs, \
             patch("aec.lib.discovery_hooks.discover_available") as mock_avail:
            mock_dirs.return_value = {
                "agents": Path("/fake/agents"),
                "skills": Path("/fake/skills"),
            }
            # discover_available returns catalog items
            mock_avail.side_effect = lambda src, item_type: (
                _mock_catalog() if item_type == "agents" else {}
            )
            # Make source dirs "exist"
            with patch.object(Path, "exists", return_value=True):
                scope = Scope(is_global=True, repo_path=None)
                quick_scan_notification(scope)

        captured = capsys.readouterr()
        assert "1 untracked item matching AEC catalog names" in captured.out
        assert "aec discover -g" in captured.out

    def test_silent_when_no_matches(self, scan_env, capsys):
        """No output when no local items match the catalog."""
        # Create a local agent that does NOT match any catalog name
        (scan_env["agents_dir"] / "totally-custom-thing.md").touch()

        with patch("aec.lib.discovery_hooks.get_source_dirs") as mock_dirs, \
             patch("aec.lib.discovery_hooks.discover_available") as mock_avail:
            mock_dirs.return_value = {
                "agents": Path("/fake/agents"),
                "skills": Path("/fake/skills"),
            }
            mock_avail.side_effect = lambda src, item_type: (
                _mock_catalog() if item_type == "agents" else {}
            )
            with patch.object(Path, "exists", return_value=True):
                scope = Scope(is_global=True, repo_path=None)
                quick_scan_notification(scope)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_silent_when_all_dismissed(self, scan_env, capsys):
        """No output when all matches are dismissed."""
        (scan_env["agents_dir"] / "engineering-backend-architect.md").touch()

        # Write dismissal file
        dismissed = {
            "schemaVersion": 1,
            "items": {
                "engineering-backend-architect.md": {
                    "dismissedAt": "2026-04-10T18:00:00Z",
                    "matchedCatalogItem": "backend-architect",
                }
            },
        }
        (scan_env["aec_home"] / "dismissed-agents.json").write_text(
            json.dumps(dismissed)
        )

        with patch("aec.lib.discovery_hooks.get_source_dirs") as mock_dirs, \
             patch("aec.lib.discovery_hooks.discover_available") as mock_avail:
            mock_dirs.return_value = {
                "agents": Path("/fake/agents"),
                "skills": Path("/fake/skills"),
            }
            mock_avail.side_effect = lambda src, item_type: (
                _mock_catalog() if item_type == "agents" else {}
            )
            with patch.object(Path, "exists", return_value=True):
                scope = Scope(is_global=True, repo_path=None)
                quick_scan_notification(scope)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_silent_for_local_scope(self, scan_env, capsys):
        """No output for local (non-global) scope."""
        (scan_env["agents_dir"] / "engineering-backend-architect.md").touch()

        scope = Scope(is_global=False, repo_path=Path("/some/repo"))
        quick_scan_notification(scope)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_never_raises_exceptions(self, capsys):
        """Even with broken dependencies, quick_scan_notification must not raise."""
        scope = Scope(is_global=True, repo_path=None)

        with patch(
            "aec.lib.discovery_hooks._quick_scan_notification_impl",
            side_effect=RuntimeError("boom"),
        ):
            # Should not raise
            quick_scan_notification(scope)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_correct_count_with_multiple_matches(self, scan_env, capsys):
        """Count reflects all matching untracked items across types."""
        # Two matching agents
        (scan_env["agents_dir"] / "engineering-backend-architect.md").touch()
        (scan_env["agents_dir"] / "engineering-code-reviewer.md").touch()

        with patch("aec.lib.discovery_hooks.get_source_dirs") as mock_dirs, \
             patch("aec.lib.discovery_hooks.discover_available") as mock_avail:
            mock_dirs.return_value = {
                "agents": Path("/fake/agents"),
                "skills": Path("/fake/skills"),
            }
            mock_avail.side_effect = lambda src, item_type: (
                _mock_catalog() if item_type == "agents" else {}
            )
            with patch.object(Path, "exists", return_value=True):
                scope = Scope(is_global=True, repo_path=None)
                quick_scan_notification(scope)

        captured = capsys.readouterr()
        assert "2 untracked items matching AEC catalog names" in captured.out

    def test_skips_already_installed_items(self, scan_env, capsys):
        """Items that are already installed are not counted as untracked."""
        (scan_env["agents_dir"] / "engineering-backend-architect.md").touch()

        # Mark it as installed in the manifest
        manifest = {
            "manifestVersion": 2,
            "global": {
                "skills": {},
                "agents": {
                    "engineering-backend-architect.md": {"version": "1.0.0"}
                },
                "rules": {},
            },
            "repos": {},
        }
        (scan_env["aec_home"] / "installed-manifest.json").write_text(
            json.dumps(manifest)
        )

        with patch("aec.lib.discovery_hooks.get_source_dirs") as mock_dirs, \
             patch("aec.lib.discovery_hooks.discover_available") as mock_avail:
            mock_dirs.return_value = {
                "agents": Path("/fake/agents"),
                "skills": Path("/fake/skills"),
            }
            mock_avail.side_effect = lambda src, item_type: (
                _mock_catalog() if item_type == "agents" else {}
            )
            with patch.object(Path, "exists", return_value=True):
                scope = Scope(is_global=True, repo_path=None)
                quick_scan_notification(scope)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_handles_empty_source_dirs(self, scan_env, capsys):
        """No crash when get_source_dirs returns empty."""
        with patch("aec.lib.discovery_hooks.get_source_dirs", return_value={}):
            scope = Scope(is_global=True, repo_path=None)
            quick_scan_notification(scope)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_singular_item_message(self, scan_env, capsys):
        """Message uses singular 'item' when count is 1."""
        (scan_env["agents_dir"] / "engineering-backend-architect.md").touch()

        with patch("aec.lib.discovery_hooks.get_source_dirs") as mock_dirs, \
             patch("aec.lib.discovery_hooks.discover_available") as mock_avail:
            mock_dirs.return_value = {
                "agents": Path("/fake/agents"),
                "skills": Path("/fake/skills"),
            }
            mock_avail.side_effect = lambda src, item_type: (
                _mock_catalog() if item_type == "agents" else {}
            )
            with patch.object(Path, "exists", return_value=True):
                scope = Scope(is_global=True, repo_path=None)
                quick_scan_notification(scope)

        captured = capsys.readouterr()
        assert "1 untracked item matching" in captured.out
        # Should NOT say "items" (plural)
        assert "1 untracked items" not in captured.out
