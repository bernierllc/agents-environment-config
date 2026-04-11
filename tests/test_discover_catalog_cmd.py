"""Tests for aec discover (catalog discovery) command."""

import json
import pytest
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from unittest.mock import patch


@dataclass
class FakeMatchResult:
    """Minimal MatchResult stand-in for testing."""
    local_name: str = ""
    local_path: str = ""
    catalog_item: str = ""
    catalog_version: str = ""
    catalog_hash: str = ""
    local_hash: str = ""
    match_type: str = "exact"
    similarity: Optional[float] = None
    scan_depth: int = 1
    item_type: str = "agents"


@pytest.fixture
def discover_env(temp_dir, monkeypatch):
    """Set up environment for discover catalog tests."""
    monkeypatch.setattr(Path, "home", lambda: temp_dir)

    aec_home = temp_dir / ".agents-environment-config"
    aec_home.mkdir()

    # Create a tracked project with .aec.json
    project = temp_dir / "projects" / "my-app"
    (project / ".claude" / "agents").mkdir(parents=True)
    (project / ".claude" / "skills").mkdir(parents=True)
    (project / ".agent-rules").mkdir(parents=True)
    aec_json = {
        "version": "1.0.0",
        "project": {"name": "my-app", "description": ""},
        "installed": {"skills": {}, "rules": {}, "agents": {}},
    }
    (project / ".aec.json").write_text(json.dumps(aec_json))

    log = aec_home / "setup-repo-locations.txt"
    log.write_text(f"2026-04-04T00:00:00Z|2.5.4|{project.resolve()}\n")

    # Create the AEC source repo
    repo = temp_dir / "aec-repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "aec").mkdir()
    (repo / ".agent-rules").mkdir()
    (repo / ".claude" / "agents").mkdir(parents=True)
    (repo / ".claude" / "skills").mkdir(parents=True)

    monkeypatch.chdir(project)

    return {
        "home": temp_dir,
        "project": project,
        "aec_home": aec_home,
        "repo": repo,
    }


P = "aec.commands.discover_catalog"


def _apply_patches(stack, scan_results=None, local_items=None, catalog_hashes=None):
    """Apply standard patches via an ExitStack and return the mocks dict."""
    if scan_results is None:
        scan_results = []
    if local_items is None:
        local_items = []
    if catalog_hashes is None:
        catalog_hashes = {"agents": {}, "skills": {}, "rules": {}}

    mocks = {}
    mocks["get_source_dirs"] = stack.enter_context(patch(f"{P}.get_source_dirs", return_value={
        "skills": Path("/fake/skills"),
        "rules": Path("/fake/rules"),
        "agents": Path("/fake/agents"),
    }))
    mocks["discover_available"] = stack.enter_context(patch(f"{P}.discover_available", return_value={}))
    mocks["load_catalog_hashes"] = stack.enter_context(patch(f"{P}.load_catalog_hashes", return_value=catalog_hashes))
    mocks["regenerate_if_missing"] = stack.enter_context(patch(f"{P}.regenerate_if_missing", return_value=catalog_hashes))
    mocks["scan_local_items"] = stack.enter_context(patch(f"{P}.scan_local_items", return_value=local_items))
    mocks["scan"] = stack.enter_context(patch(f"{P}.scan", return_value=scan_results))
    mocks["is_dismissed"] = stack.enter_context(patch(f"{P}.is_dismissed", return_value=False))
    mocks["clear_dismissals"] = stack.enter_context(patch(f"{P}.clear_dismissals"))
    mocks["prune_stale"] = stack.enter_context(patch(f"{P}.prune_stale"))
    mocks["save_dismissal"] = stack.enter_context(patch(f"{P}.save_dismissal"))
    mocks["backup_item"] = stack.enter_context(patch(f"{P}.backup_item"))
    mocks["ensure_backup_gitignore"] = stack.enter_context(patch(f"{P}.ensure_backup_gitignore"))
    # Patch load_aec_json in _run_scan to avoid re-reading from disk
    mocks["load_aec_json_scan"] = stack.enter_context(patch(
        "aec.commands.discover_catalog.load_aec_json",
        return_value={"installed": {"agents": {}, "skills": {}, "rules": {}}},
    ))
    return mocks


class TestDryRun:
    """Dry-run mode: prints results, no writes."""

    def test_dry_run_prints_results_no_writes(self, discover_env, capsys):
        """Dry run shows results but does not install or dismiss anything."""
        exact = FakeMatchResult(
            local_name="my-agent.md",
            catalog_item="engineering-agent",
            match_type="exact",
            item_type="agents",
        )
        local_item = {"name": "my-agent.md", "path": "/fake/my-agent.md", "is_dir": False}

        with ExitStack() as stack:
            mocks = _apply_patches(stack, scan_results=[exact], local_items=[local_item])
            from aec.commands.discover_catalog import run_discover
            run_discover(dry_run=True, depth=1)

            out = capsys.readouterr().out
            assert "dry run" in out.lower()
            mocks["save_dismissal"].assert_not_called()

    def test_dry_run_does_not_call_install(self, discover_env, capsys):
        """Dry run never calls run_install."""
        exact = FakeMatchResult(
            local_name="my-skill/",
            catalog_item="my-skill",
            match_type="exact",
            item_type="skills",
        )
        local_item = {"name": "my-skill/", "path": "/fake/my-skill", "is_dir": True}

        with ExitStack() as stack:
            mocks = _apply_patches(stack, scan_results=[exact], local_items=[local_item])
            mock_install = stack.enter_context(patch(f"{P}._install_item"))

            from aec.commands.discover_catalog import run_discover
            run_discover(dry_run=True, depth=1)
            mock_install.assert_not_called()


class TestYesMode:
    """--yes mode: installs exact matches, skips non-exact."""

    def test_yes_installs_exact_skips_similar(self, discover_env, capsys):
        """--yes installs exact matches and dismisses non-exact."""
        exact = FakeMatchResult(
            local_name="exact-agent.md",
            local_path="/fake/exact-agent.md",
            catalog_item="exact-agent",
            match_type="exact",
            item_type="agents",
        )
        similar = FakeMatchResult(
            local_name="similar-agent.md",
            local_path="/fake/similar-agent.md",
            catalog_item="catalog-agent",
            match_type="similar",
            similarity=0.85,
            item_type="agents",
        )
        local_item = {"name": "x", "path": "/fake/x", "is_dir": False}

        with ExitStack() as stack:
            mocks = _apply_patches(stack, scan_results=[exact, similar], local_items=[local_item])
            mock_install_item = stack.enter_context(patch(f"{P}._install_item"))

            from aec.commands.discover_catalog import run_discover
            run_discover(yes=True, depth=1)

            # Exact match should trigger install
            assert mock_install_item.called
            # save_dismissal should be called for each non-exact result
            # (scan returns [exact, similar] for each of 3 item types)
            assert mocks["save_dismissal"].call_count >= 1


class TestDepthValidation:
    """Depth validation rejects invalid values."""

    def test_invalid_depth_exits(self, discover_env):
        """Depth outside 1-3 should cause SystemExit."""
        with ExitStack() as stack:
            _apply_patches(stack)
            from aec.commands.discover_catalog import run_discover
            with pytest.raises(SystemExit):
                run_discover(depth=5)

    def test_depth_zero_exits(self, discover_env):
        """Depth 0 should cause SystemExit."""
        with ExitStack() as stack:
            _apply_patches(stack)
            from aec.commands.discover_catalog import run_discover
            with pytest.raises(SystemExit):
                run_discover(depth=0)

    def test_valid_depths_accepted(self, discover_env, capsys):
        """Depths 1, 2, 3 should not raise."""
        for d in (1, 2, 3):
            with ExitStack() as stack:
                _apply_patches(stack)
                from aec.commands.discover_catalog import run_discover
                run_discover(depth=d)  # should not raise


class TestMissingAecJson:
    """Missing .aec.json shows error message."""

    def test_missing_aec_json_errors(self, temp_dir, monkeypatch, capsys):
        """Local scope without .aec.json should error."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        # Create a project dir without .aec.json
        project = temp_dir / "projects" / "no-aec"
        project.mkdir(parents=True)
        monkeypatch.chdir(project)

        from aec.commands.discover_catalog import run_discover
        with pytest.raises(SystemExit):
            run_discover(global_flag=False, depth=1)

        out = capsys.readouterr().out
        assert "not tracked by AEC" in out


class TestZeroMatches:
    """Zero matches shows appropriate message."""

    def test_no_matches_message(self, discover_env, capsys):
        """When scan returns nothing, show 'No similar items found.'"""
        with ExitStack() as stack:
            _apply_patches(stack)
            from aec.commands.discover_catalog import run_discover
            run_discover(depth=1)

        out = capsys.readouterr().out
        assert "No similar items found" in out


class TestGlobalFlag:
    """Global flag uses global scope."""

    def test_global_flag_skips_aec_json_check(self, temp_dir, monkeypatch, capsys):
        """With -g, should not require .aec.json."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        # No .aec.json anywhere, but create minimal home structure
        project = temp_dir / "projects" / "whatever"
        project.mkdir(parents=True)
        monkeypatch.chdir(project)

        with ExitStack() as stack:
            _apply_patches(stack)
            from aec.commands.discover_catalog import run_discover
            run_discover(global_flag=True, depth=1)

        out = capsys.readouterr().out
        assert "not tracked by AEC" not in out


class TestRediscoverFlag:
    """--rediscover clears dismissals before scan."""

    def test_rediscover_clears_dismissals(self, discover_env, capsys):
        """--rediscover should call clear_dismissals for each item type."""
        with ExitStack() as stack:
            mocks = _apply_patches(stack)
            from aec.commands.discover_catalog import run_discover
            run_discover(rediscover=True, depth=1)

        # clear_dismissals should be called for each item type
        assert mocks["clear_dismissals"].call_count == 3  # agents, skills, rules


class TestContributionMessage:
    """Contribution message shown when items are skipped."""

    def test_contribution_urls_shown_for_dismissed(self, discover_env, capsys):
        """When items are dismissed in --yes mode, contribution URLs are shown."""
        agent = FakeMatchResult(
            local_name="custom-agent.md",
            local_path="/fake/custom-agent.md",
            catalog_item="some-agent",
            match_type="similar",
            similarity=0.8,
            item_type="agents",
        )
        local_item = {"name": "x", "path": "/fake/x", "is_dir": False}

        with ExitStack() as stack:
            mocks = _apply_patches(stack, scan_results=[agent], local_items=[local_item])
            stack.enter_context(patch(f"{P}._install_item"))

            from aec.commands.discover_catalog import run_discover
            run_discover(yes=True, depth=1)

        out = capsys.readouterr().out
        assert "skipped" in out.lower() or "Skipped" in out
        assert "CONTRIBUTING" in out


class TestRunScan:
    """Unit tests for the _run_scan helper."""

    def test_run_scan_returns_results(self, discover_env):
        """_run_scan returns match results from scan()."""
        from aec.lib.scope import Scope

        scope = Scope(is_global=False, repo_path=discover_env["project"])

        fake_result = FakeMatchResult(
            local_name="test.md",
            catalog_item="catalog-test",
            match_type="exact",
        )
        local_item = {"name": "test.md", "path": "/fake/test.md", "is_dir": False}

        catalog = {"agents": {}, "skills": {}, "rules": {}}
        catalog_hashes = {"agents": {}, "skills": {}, "rules": {}}

        with ExitStack() as stack:
            mocks = _apply_patches(stack, scan_results=[fake_result], local_items=[local_item])

            from aec.commands.discover_catalog import _run_scan
            results = _run_scan(scope, depth=2, rediscover=False,
                                catalog=catalog, catalog_hashes=catalog_hashes)

        # Should have results (3 types scanned, each returns [fake_result])
        assert len(results) >= 1


class TestPresentResults:
    """Unit tests for the _present_results helper."""

    def test_present_empty_results(self, discover_env, capsys):
        """Empty results shows 'No similar items found.'"""
        from aec.commands.discover_catalog import _present_results
        from aec.lib.scope import Scope

        scope = Scope(is_global=False, repo_path=discover_env["project"])
        _present_results([], scope)

        out = capsys.readouterr().out
        assert "No similar items found" in out

    def test_present_results_dry_run(self, discover_env, capsys):
        """Dry run shows items but says 'dry run'."""
        from aec.commands.discover_catalog import _present_results
        from aec.lib.scope import Scope

        scope = Scope(is_global=False, repo_path=discover_env["project"])
        results = [
            FakeMatchResult(
                local_name="agent.md",
                catalog_item="catalog-agent",
                match_type="exact",
                item_type="agents",
            )
        ]
        _present_results(results, scope, dry_run=True)

        out = capsys.readouterr().out
        assert "Found 1" in out
        assert "dry run" in out.lower()


class TestDepthPrompt:
    """Tests for the interactive depth prompt."""

    def test_prompt_depth_default(self, monkeypatch):
        """Empty input returns default depth 2."""
        from aec.commands.discover_catalog import _prompt_depth
        monkeypatch.setattr("builtins.input", lambda: "")
        assert _prompt_depth() == 2

    def test_prompt_depth_explicit(self, monkeypatch):
        """Explicit '3' returns depth 3."""
        from aec.commands.discover_catalog import _prompt_depth
        monkeypatch.setattr("builtins.input", lambda: "3")
        assert _prompt_depth() == 3

    def test_prompt_depth_invalid(self, monkeypatch):
        """Invalid input exits."""
        from aec.commands.discover_catalog import _prompt_depth
        monkeypatch.setattr("builtins.input", lambda: "7")
        with pytest.raises(SystemExit):
            _prompt_depth()

    def test_prompt_depth_eof(self, monkeypatch):
        """EOFError returns default depth 2."""
        from aec.commands.discover_catalog import _prompt_depth

        def raise_eof():
            raise EOFError

        monkeypatch.setattr("builtins.input", raise_eof)
        assert _prompt_depth() == 2


class TestFormatMatch:
    """Tests for match result formatting."""

    def test_exact_match_format(self):
        """Exact match shows checkmark."""
        from aec.commands.discover_catalog import _format_match
        result = FakeMatchResult(
            local_name="my-agent.md",
            match_type="exact",
        )
        formatted = _format_match(1, result)
        assert "my-agent.md" in formatted
        assert "Exact match" in formatted

    def test_similar_match_format(self):
        """Similar match shows percentage."""
        from aec.commands.discover_catalog import _format_match
        result = FakeMatchResult(
            local_name="custom.md",
            catalog_item="catalog-item",
            match_type="similar",
            similarity=0.87,
        )
        formatted = _format_match(2, result)
        assert "87%" in formatted
        assert "catalog-item" in formatted

    def test_modified_match_format(self):
        """Modified match shows warning."""
        from aec.commands.discover_catalog import _format_match
        result = FakeMatchResult(
            local_name="skill/",
            match_type="modified",
        )
        formatted = _format_match(3, result)
        assert "Modified" in formatted

    def test_renamed_match_format(self):
        """Renamed match shows the catalog name."""
        from aec.commands.discover_catalog import _format_match
        result = FakeMatchResult(
            local_name="old-name.md",
            catalog_item="new-name",
            match_type="renamed",
        )
        formatted = _format_match(4, result)
        assert "Renamed" in formatted
        assert "new-name" in formatted
