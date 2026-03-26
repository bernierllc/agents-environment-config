"""Tests for prune_stale tracking cleanup."""

from pathlib import Path

import pytest


class TestPruneStale:
    """Test prune_stale() in tracking.py."""

    def _setup_tracking(self, temp_dir, monkeypatch):
        """Helper to set up isolated tracking environment."""
        aec_home = temp_dir / ".agents-environment-config"
        aec_home.mkdir(parents=True)
        log_file = aec_home / "setup-repo-locations.txt"
        monkeypatch.setattr("aec.lib.tracking.AEC_HOME", aec_home)
        monkeypatch.setattr("aec.lib.tracking.AEC_SETUP_LOG", log_file)
        monkeypatch.setattr("aec.lib.tracking.AEC_README", aec_home / "README.md")
        return log_file

    def test_prune_removes_nonexistent_paths(self, temp_dir, monkeypatch):
        """prune_stale() removes entries where the path doesn't exist."""
        from aec.lib.tracking import prune_stale

        log_file = self._setup_tracking(temp_dir, monkeypatch)

        # Create one real project and one fake
        real_project = temp_dir / "real-project"
        real_project.mkdir()
        fake_project = temp_dir / "nonexistent-project"

        log_file.write_text(
            f"2026-01-01T00:00:00Z|2.0.0|{real_project}\n"
            f"2026-01-01T00:00:00Z|2.0.0|{fake_project}\n"
        )

        pruned = prune_stale()
        assert len(pruned) == 1
        assert pruned[0].path == fake_project

        # Verify the real project is still tracked
        content = log_file.read_text()
        assert str(real_project) in content
        assert str(fake_project) not in content

    def test_prune_no_stale_entries(self, temp_dir, monkeypatch):
        """prune_stale() returns empty list when all paths exist."""
        from aec.lib.tracking import prune_stale

        log_file = self._setup_tracking(temp_dir, monkeypatch)

        project = temp_dir / "my-project"
        project.mkdir()

        log_file.write_text(f"2026-01-01T00:00:00Z|2.0.0|{project}\n")

        pruned = prune_stale()
        assert len(pruned) == 0

    def test_prune_empty_log(self, temp_dir, monkeypatch):
        """prune_stale() handles empty log file."""
        from aec.lib.tracking import prune_stale

        log_file = self._setup_tracking(temp_dir, monkeypatch)
        log_file.touch()

        pruned = prune_stale()
        assert len(pruned) == 0

    def test_prune_no_log_file(self, temp_dir, monkeypatch):
        """prune_stale() handles missing log file."""
        from aec.lib.tracking import prune_stale

        self._setup_tracking(temp_dir, monkeypatch)
        # Don't create the log file

        pruned = prune_stale()
        assert len(pruned) == 0

    def test_prune_dry_run_does_not_modify(self, temp_dir, monkeypatch):
        """prune_stale(dry_run=True) reports but doesn't change the file."""
        from aec.lib.tracking import prune_stale

        log_file = self._setup_tracking(temp_dir, monkeypatch)

        fake_project = temp_dir / "nonexistent"
        original_content = f"2026-01-01T00:00:00Z|2.0.0|{fake_project}\n"
        log_file.write_text(original_content)

        pruned = prune_stale(dry_run=True)
        assert len(pruned) == 1

        # File should be unchanged
        assert log_file.read_text() == original_content

    def test_prune_all_stale_results_in_empty_file(self, temp_dir, monkeypatch):
        """prune_stale() produces empty file when all entries are stale."""
        from aec.lib.tracking import prune_stale

        log_file = self._setup_tracking(temp_dir, monkeypatch)

        log_file.write_text(
            f"2026-01-01T00:00:00Z|2.0.0|{temp_dir}/fake1\n"
            f"2026-01-01T00:00:00Z|2.0.0|{temp_dir}/fake2\n"
        )

        pruned = prune_stale()
        assert len(pruned) == 2
        assert log_file.read_text() == ""

    def test_prune_preserves_malformed_lines(self, temp_dir, monkeypatch):
        """prune_stale() keeps lines that don't have 3 pipe-separated fields."""
        from aec.lib.tracking import prune_stale

        log_file = self._setup_tracking(temp_dir, monkeypatch)

        real_project = temp_dir / "real"
        real_project.mkdir()

        log_file.write_text(
            f"malformed-line\n"
            f"2026-01-01T00:00:00Z|2.0.0|{real_project}\n"
            f"2026-01-01T00:00:00Z|2.0.0|{temp_dir}/fake\n"
        )

        pruned = prune_stale()
        assert len(pruned) == 1

        content = log_file.read_text()
        assert "malformed-line" in content
        assert str(real_project) in content


class TestPruneCommand:
    """Test the repo prune CLI command."""

    def test_prune_command_registered(self):
        """aec repo prune command exists."""
        from aec.commands.repo import prune
        assert callable(prune)

    def test_prune_no_stale_prints_clean(self, temp_dir, monkeypatch, capsys):
        """prune() prints clean message when no stale entries."""
        from aec.commands.repo import prune

        # Point tracking to isolated temp dir
        aec_home = temp_dir / ".agents-environment-config"
        aec_home.mkdir(parents=True)
        log_file = aec_home / "setup-repo-locations.txt"

        project = temp_dir / "real"
        project.mkdir()
        log_file.write_text(f"2026-01-01T00:00:00Z|2.0.0|{project}\n")

        monkeypatch.setattr("aec.lib.tracking.AEC_SETUP_LOG", log_file)

        prune(yes=True)

        output = capsys.readouterr().out
        assert "clean" in output.lower() or "No stale" in output
