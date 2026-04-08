"""Tests for aec test CLI command group."""

import subprocess
import sys

import pytest


class TestCLIRegistration:
    """Verify the test command group is registered in the CLI."""

    def test_test_help_shows_subcommands(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "test", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        output = result.stdout
        assert "run" in output
        assert "schedule" in output
        assert "status" in output
        assert "enable" in output
        assert "disable" in output
        assert "report" in output
        assert "detect" in output

    def test_top_level_help_shows_test(self):
        result = subprocess.run(
            [sys.executable, "-m", "aec", "--help"],
            capture_output=True, text=True,
        )
        assert "test" in result.stdout


class TestRunTestStatus:
    """Test run_test_status with and without .aec.json."""

    def test_status_no_aec_json(self, tmp_path, monkeypatch):
        """Status in a project with no .aec.json shows appropriate message."""
        from aec.commands.test_cmd import run_test_status

        monkeypatch.setattr(
            "aec.lib.scope.find_tracked_repo",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "aec.lib.aec_json.load_aec_json",
            lambda p: None,
        )

        captured = []
        monkeypatch.setattr(
            "aec.lib.console.Console.info",
            staticmethod(lambda msg: captured.append(msg)),
        )

        run_test_status(global_flag=False)
        assert any("No .aec.json" in msg for msg in captured)

    def test_status_with_aec_json(self, tmp_path, monkeypatch):
        """Status in a project with .aec.json shows test config."""
        from aec.commands.test_cmd import run_test_status

        aec_data = {
            "project": "test-project",
            "test": {
                "suites": {
                    "unit": {"command": "pytest tests/"},
                },
                "prerequisites": ["docker"],
                "scheduled": True,
            },
        }

        monkeypatch.setattr(
            "aec.lib.scope.find_tracked_repo",
            lambda: tmp_path,
        )
        monkeypatch.setattr(
            "aec.lib.aec_json.load_aec_json",
            lambda p: aec_data,
        )

        printed = []
        monkeypatch.setattr(
            "aec.lib.console.Console.print",
            staticmethod(lambda msg: printed.append(msg)),
        )
        monkeypatch.setattr(
            "aec.lib.console.Console.subheader",
            staticmethod(lambda msg: printed.append(msg)),
        )
        monkeypatch.setattr(
            "aec.lib.console.Console.info",
            staticmethod(lambda msg: printed.append(msg)),
        )

        run_test_status(global_flag=False)

        output = "\n".join(printed)
        assert "pytest tests/" in output
        assert "docker" in output


class TestRunTestDetect:
    """Test run_test_detect discovers frameworks."""

    def test_detect_finds_jest(self, tmp_path, monkeypatch):
        """Detect finds a jest config file and updates .aec.json."""
        from aec.commands.test_cmd import run_test_detect

        # Create jest config
        (tmp_path / "jest.config.ts").write_text("export default {}")

        monkeypatch.setattr(
            "aec.lib.scope.find_tracked_repo",
            lambda: tmp_path,
        )

        detected_frameworks = [
            {"name": "jest", "command": "npx jest"},
        ]
        detected_scripts = []

        monkeypatch.setattr(
            "aec.lib.test_detection.detect_test_frameworks",
            lambda p: detected_frameworks,
        )
        monkeypatch.setattr(
            "aec.lib.test_detection.scan_test_scripts",
            lambda p: detected_scripts,
        )

        saved_data = {}

        def mock_save(path, data):
            saved_data.update(data)

        monkeypatch.setattr(
            "aec.lib.aec_json.load_aec_json",
            lambda p: {},
        )
        monkeypatch.setattr(
            "aec.lib.aec_json.save_aec_json",
            mock_save,
        )

        success_msgs = []
        monkeypatch.setattr(
            "aec.lib.console.Console.success",
            staticmethod(lambda msg: success_msgs.append(msg)),
        )
        monkeypatch.setattr(
            "aec.lib.console.Console.info",
            staticmethod(lambda msg: None),
        )
        monkeypatch.setattr(
            "aec.lib.console.Console.subheader",
            staticmethod(lambda msg: None),
        )
        monkeypatch.setattr(
            "aec.lib.console.Console.print",
            staticmethod(lambda msg: None),
        )

        run_test_detect()

        assert any("Updated" in msg for msg in success_msgs)
        assert "test" in saved_data
        assert "jest" in saved_data["test"].get("suites", {})


class TestRunTestReport:
    """Test run_test_report with no reports."""

    def test_report_no_reports(self, tmp_path, monkeypatch):
        """Report with no reports directory shows appropriate message."""
        from aec.commands.test_cmd import run_test_report

        monkeypatch.setattr(
            "aec.lib.config.AEC_HOME",
            tmp_path,
        )

        info_msgs = []
        monkeypatch.setattr(
            "aec.lib.console.Console.info",
            staticmethod(lambda msg: info_msgs.append(msg)),
        )

        run_test_report(global_flag=False)

        assert any("No test reports" in msg for msg in info_msgs)

    def test_report_no_reports_global(self, tmp_path, monkeypatch):
        """Global report with no reports directory shows appropriate message."""
        from aec.commands.test_cmd import run_test_report

        monkeypatch.setattr(
            "aec.lib.config.AEC_HOME",
            tmp_path,
        )

        info_msgs = []
        monkeypatch.setattr(
            "aec.lib.console.Console.info",
            staticmethod(lambda msg: info_msgs.append(msg)),
        )

        run_test_report(global_flag=True)

        assert any("No test reports" in msg for msg in info_msgs)
