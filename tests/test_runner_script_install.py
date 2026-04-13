"""Tests for copying the generic scheduled runner into AEC_HOME."""

import filecmp
from pathlib import Path


class TestRunnerScriptInstall:
    """Tests for aec.lib.runner_script_install."""

    def test_ensure_copies_packaged_entrypoint(self, tmp_path: Path) -> None:
        from aec.lib.runner_script_install import (
            ensure_runner_script,
            scheduled_runner_source_path,
        )

        dest = tmp_path / "runner.py"
        out = ensure_runner_script(dest)
        assert out == dest.resolve()
        assert dest.is_file()
        assert filecmp.cmp(scheduled_runner_source_path(), dest, shallow=False)
        assert "run_all_projects" in dest.read_text(encoding="utf-8")

    def test_ensure_idempotent_when_bytes_match(self, tmp_path: Path) -> None:
        from aec.lib.runner_script_install import ensure_runner_script

        dest = tmp_path / "runner.py"
        ensure_runner_script(dest)
        first_mtime = dest.stat().st_mtime_ns
        ensure_runner_script(dest)
        assert dest.stat().st_mtime_ns == first_mtime

    def test_ensure_rewrites_when_content_differs(self, tmp_path: Path) -> None:
        from aec.lib.runner_script_install import ensure_runner_script

        dest = tmp_path / "runner.py"
        dest.write_text("# stale\n", encoding="utf-8")
        ensure_runner_script(dest)
        assert "run_all_projects" in dest.read_text(encoding="utf-8")
