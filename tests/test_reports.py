"""Tests for aec.lib.reports module — report generation and management."""

import time
from datetime import datetime, timezone
from pathlib import Path

import pytest


class TestCreateReportDir:
    """Test create_report_dir function."""

    def test_creates_directory(self, temp_dir):
        """Should create a timestamped directory."""
        from aec.lib.reports import create_report_dir

        ts = "2026-04-08T02:00:00Z"
        result = create_report_dir(temp_dir, ts)
        assert result.exists()
        assert result.is_dir()
        assert result == temp_dir / ts

    def test_creates_parent_dirs(self, temp_dir):
        """Should create intermediate parent directories."""
        from aec.lib.reports import create_report_dir

        ts = "2026-04-08T02:00:00Z"
        nested = temp_dir / "deep" / "nested" / "path"
        result = create_report_dir(nested, ts)
        assert result.exists()
        assert result == nested / ts

    def test_idempotent(self, temp_dir):
        """Should not error if directory already exists."""
        from aec.lib.reports import create_report_dir

        ts = "2026-04-08T02:00:00Z"
        first = create_report_dir(temp_dir, ts)
        second = create_report_dir(temp_dir, ts)
        assert first == second
        assert first.exists()


class TestWriteSuiteOutput:
    """Test write_suite_output function."""

    def test_creates_file_with_correct_name(self, temp_dir):
        """Should create {project}_test_output.txt."""
        from aec.lib.reports import write_suite_output

        result = write_suite_output(temp_dir, "earnlearn", "test output here")
        assert result.name == "earnlearn_test_output.txt"
        assert result.parent == temp_dir

    def test_writes_content_correctly(self, temp_dir):
        """Should write the exact output string to the file."""
        from aec.lib.reports import write_suite_output

        content = "PASS: 42 tests passed\nFAIL: 0 tests failed\n"
        result = write_suite_output(temp_dir, "myproject", content)
        assert result.read_text() == content


class TestGenerateSummary:
    """Test generate_summary function."""

    def _make_report_dir(self, temp_dir, ts="2026-04-08T02:00:00Z"):
        """Helper to create a report dir with a known timestamp."""
        report_dir = temp_dir / ts
        report_dir.mkdir(parents=True, exist_ok=True)
        return report_dir

    def _sample_results(self):
        """Return sample results for testing."""
        return [
            {
                "project": "barevents",
                "suite": "unit",
                "status": "passed",
                "duration_seconds": 23.4,
                "exit_code": 0,
                "skip_reason": None,
            },
            {
                "project": "barevents",
                "suite": "integration",
                "status": "skipped",
                "duration_seconds": None,
                "exit_code": None,
                "skip_reason": "prerequisite: docker not available",
            },
            {
                "project": "earnlearn",
                "suite": "unit",
                "status": "passed",
                "duration_seconds": 45.2,
                "exit_code": 0,
                "skip_reason": None,
            },
            {
                "project": "earnlearn",
                "suite": "integration",
                "status": "failed",
                "duration_seconds": 12.1,
                "exit_code": 1,
                "skip_reason": None,
            },
        ]

    def test_creates_summary_txt(self, temp_dir):
        """Should create summary.txt in the report directory."""
        from aec.lib.reports import generate_summary

        report_dir = self._make_report_dir(temp_dir)
        result = generate_summary(
            report_dir, self._sample_results(), [], [], ["barevents", "earnlearn"],
            42, "auto", 0,
        )
        assert result.name == "summary.txt"
        assert result.exists()

    def test_includes_project_results(self, temp_dir):
        """Should include project names and suite results."""
        from aec.lib.reports import generate_summary

        report_dir = self._make_report_dir(temp_dir)
        generate_summary(
            report_dir, self._sample_results(), [], [], ["barevents", "earnlearn"],
            42, "auto", 0,
        )
        content = (report_dir / "summary.txt").read_text()
        assert "barevents" in content
        assert "earnlearn" in content
        assert "unit" in content
        assert "integration" in content

    def test_shows_correct_symbols(self, temp_dir):
        """Should use ✓ for passed, ✗ for failed, ⊘ for skipped."""
        from aec.lib.reports import generate_summary

        report_dir = self._make_report_dir(temp_dir)
        generate_summary(
            report_dir, self._sample_results(), [], [], ["barevents", "earnlearn"],
            42, "auto", 0,
        )
        content = (report_dir / "summary.txt").read_text()
        assert "✓" in content
        assert "✗" in content
        assert "⊘" in content

    def test_includes_note_when_retention_manual(self, temp_dir):
        """Should include 'Note: N days' line when retention_mode is 'manual'."""
        from aec.lib.reports import generate_summary

        report_dir = self._make_report_dir(temp_dir)
        generate_summary(
            report_dir, self._sample_results(), [], [], ["barevents"],
            42, "manual", 12,
        )
        content = (report_dir / "summary.txt").read_text()
        assert "Note: 12 days of reports exist" in content

    def test_omits_note_when_retention_auto(self, temp_dir):
        """Should not include 'Note:' line when retention_mode is 'auto'."""
        from aec.lib.reports import generate_summary

        report_dir = self._make_report_dir(temp_dir)
        generate_summary(
            report_dir, self._sample_results(), [], [], ["barevents"],
            42, "auto", 12,
        )
        content = (report_dir / "summary.txt").read_text()
        assert "Note:" not in content

    def test_includes_port_observations_when_present(self, temp_dir):
        """Should include port observations section when list is non-empty."""
        from aec.lib.reports import generate_summary

        report_dir = self._make_report_dir(temp_dir)
        port_obs = [{"project": "earnlearn", "ports": [9229, 9230]}]
        generate_summary(
            report_dir, self._sample_results(), port_obs, [], ["barevents"],
            42, "auto", 0,
        )
        content = (report_dir / "summary.txt").read_text()
        assert "Port observations:" in content
        assert "9229" in content
        assert "9230" in content
        assert "not registered in AEC" in content

    def test_omits_port_observations_when_empty(self, temp_dir):
        """Should not include port observations section when list is empty."""
        from aec.lib.reports import generate_summary

        report_dir = self._make_report_dir(temp_dir)
        generate_summary(
            report_dir, self._sample_results(), [], [], ["barevents"],
            42, "auto", 0,
        )
        content = (report_dir / "summary.txt").read_text()
        assert "Port observations:" not in content

    def test_includes_execution_order_and_seed(self, temp_dir):
        """Should include execution order and seed in header."""
        from aec.lib.reports import generate_summary

        report_dir = self._make_report_dir(temp_dir)
        generate_summary(
            report_dir, self._sample_results(), [], [],
            ["barevents", "earnlearn", "mbernier.com"], 42, "auto", 0,
        )
        content = (report_dir / "summary.txt").read_text()
        assert "Execution order: barevents, earnlearn, mbernier.com (seed: 42)" in content

    def test_includes_process_observations_when_present(self, temp_dir):
        """Should include process observations section when list is non-empty."""
        from aec.lib.reports import generate_summary

        report_dir = self._make_report_dir(temp_dir)
        proc_obs = [{"label": "earnlearn integration", "count": 3, "pids": [42310, 42311, 42312]}]
        generate_summary(
            report_dir, self._sample_results(), [], proc_obs, ["barevents"],
            42, "auto", 0,
        )
        content = (report_dir / "summary.txt").read_text()
        assert "Process observations:" in content
        assert "3 node processes leaked" in content
        assert "42310" in content

    def test_omits_process_observations_when_empty(self, temp_dir):
        """Should not include process observations section when list is empty."""
        from aec.lib.reports import generate_summary

        report_dir = self._make_report_dir(temp_dir)
        generate_summary(
            report_dir, self._sample_results(), [], [], ["barevents"],
            42, "auto", 0,
        )
        content = (report_dir / "summary.txt").read_text()
        assert "Process observations:" not in content

    def test_failed_result_references_output_file(self, temp_dir):
        """Failed results should reference the project's test output file."""
        from aec.lib.reports import generate_summary

        report_dir = self._make_report_dir(temp_dir)
        generate_summary(
            report_dir, self._sample_results(), [], [], ["barevents", "earnlearn"],
            42, "auto", 0,
        )
        content = (report_dir / "summary.txt").read_text()
        assert "→ see earnlearn_test_output.txt" in content


class TestCountReportDays:
    """Test count_report_days function."""

    def test_counts_directories(self, temp_dir):
        """Should count the number of subdirectories."""
        from aec.lib.reports import count_report_days

        (temp_dir / "2026-04-01T00:00:00Z").mkdir()
        (temp_dir / "2026-04-02T00:00:00Z").mkdir()
        (temp_dir / "2026-04-03T00:00:00Z").mkdir()

        assert count_report_days(temp_dir) == 3

    def test_returns_zero_for_empty_dir(self, temp_dir):
        """Should return 0 for an empty directory."""
        from aec.lib.reports import count_report_days

        assert count_report_days(temp_dir) == 0

    def test_returns_zero_for_missing_dir(self, temp_dir):
        """Should return 0 if the directory doesn't exist."""
        from aec.lib.reports import count_report_days

        assert count_report_days(temp_dir / "nonexistent") == 0

    def test_ignores_files(self, temp_dir):
        """Should only count directories, not files."""
        from aec.lib.reports import count_report_days

        (temp_dir / "2026-04-01T00:00:00Z").mkdir()
        (temp_dir / "stray_file.txt").write_text("oops")

        assert count_report_days(temp_dir) == 1


class TestPruneOldReports:
    """Test prune_old_reports function."""

    def test_deletes_old_directories(self, temp_dir):
        """Should delete directories older than max_days."""
        from aec.lib.reports import prune_old_reports

        # Create an old directory (30 days ago)
        old_time = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
        old_name = old_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        old_dir = temp_dir / old_name
        old_dir.mkdir()
        (old_dir / "summary.txt").write_text("old report")

        deleted = prune_old_reports(temp_dir, max_days=7)
        assert deleted == 1
        assert not old_dir.exists()

    def test_keeps_recent_directories(self, temp_dir):
        """Should keep directories newer than max_days."""
        from aec.lib.reports import prune_old_reports

        # Create a very recent directory
        now = datetime.now(timezone.utc)
        recent_name = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        recent_dir = temp_dir / recent_name
        recent_dir.mkdir()
        (recent_dir / "summary.txt").write_text("recent report")

        deleted = prune_old_reports(temp_dir, max_days=7)
        assert deleted == 0
        assert recent_dir.exists()

    def test_returns_zero_for_missing_dir(self, temp_dir):
        """Should return 0 if base_dir doesn't exist."""
        from aec.lib.reports import prune_old_reports

        assert prune_old_reports(temp_dir / "nope", max_days=7) == 0


class TestPruneOldProfiles:
    """Test prune_old_profiles function."""

    def test_deletes_old_profile_files(self, temp_dir):
        """Should delete profile JSON files older than max_days."""
        from aec.lib.reports import prune_old_profiles

        # Create project subdirectory with an old profile
        project_dir = temp_dir / "earnlearn"
        project_dir.mkdir()
        old_profile = project_dir / "profile_old.json"
        old_profile.write_text('{"data": "old"}')

        # Set mtime to 30 days ago
        old_mtime = time.time() - (30 * 86400)
        import os

        os.utime(old_profile, (old_mtime, old_mtime))

        deleted = prune_old_profiles(temp_dir, max_days=7)
        assert deleted == 1
        assert not old_profile.exists()

    def test_keeps_recent_profiles(self, temp_dir):
        """Should keep profile JSON files newer than max_days."""
        from aec.lib.reports import prune_old_profiles

        project_dir = temp_dir / "earnlearn"
        project_dir.mkdir()
        recent_profile = project_dir / "profile_recent.json"
        recent_profile.write_text('{"data": "recent"}')

        deleted = prune_old_profiles(temp_dir, max_days=7)
        assert deleted == 0
        assert recent_profile.exists()

    def test_returns_zero_for_missing_dir(self, temp_dir):
        """Should return 0 if profiles_dir doesn't exist."""
        from aec.lib.reports import prune_old_profiles

        assert prune_old_profiles(temp_dir / "nope", max_days=7) == 0

    def test_ignores_non_json_files(self, temp_dir):
        """Should only delete .json files."""
        from aec.lib.reports import prune_old_profiles

        project_dir = temp_dir / "myproject"
        project_dir.mkdir()
        txt_file = project_dir / "notes.txt"
        txt_file.write_text("not a profile")
        old_mtime = time.time() - (30 * 86400)
        import os

        os.utime(txt_file, (old_mtime, old_mtime))

        deleted = prune_old_profiles(temp_dir, max_days=7)
        assert deleted == 0
        assert txt_file.exists()


class TestOpenReport:
    """Test open_report function."""

    def test_uses_viewers_module_when_available(self, temp_dir, monkeypatch):
        """Should use get_viewer_command from viewers module."""
        from aec.lib.reports import open_report

        report_file = temp_dir / "summary.txt"
        report_file.write_text("test")

        # Track what Popen was called with
        calls = []

        class MockPopen:
            def __init__(self, *args, **kwargs):
                calls.append((args, kwargs))

        monkeypatch.setattr("aec.lib.reports.subprocess.Popen", MockPopen)

        result = open_report(report_file, "vscode")
        assert result is True
        assert len(calls) == 1

    def test_returns_false_when_no_viewer(self, temp_dir, monkeypatch):
        """Should return False when viewer module and platform fallback unavailable."""
        from aec.lib.reports import open_report

        report_file = temp_dir / "summary.txt"
        report_file.write_text("test")

        # Make viewers module return None for the key
        import aec.lib.viewers as viewers_mod

        monkeypatch.setattr(viewers_mod, "get_viewer_command", lambda key, **kw: None)
        # Set platform to something without a fallback
        monkeypatch.setattr("aec.lib.reports.sys.platform", "win32")

        result = open_report(report_file, "nonexistent_viewer")
        assert result is False
