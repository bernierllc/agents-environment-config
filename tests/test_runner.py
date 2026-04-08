"""Tests for aec/lib/runner.py — the core test runner."""

import subprocess
import time
from pathlib import Path

import pytest


class TestExecuteSuite:
    """Tests for execute_suite()."""

    def test_captures_output_and_exit_code(self, monkeypatch):
        """execute_suite returns stdout, exit code, and status."""
        from aec.lib.runner import execute_suite

        fake_result = subprocess.CompletedProcess(
            args="echo hello",
            returncode=0,
            stdout="hello\n",
            stderr="",
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)

        result = execute_suite(Path("/tmp"), "unit", {"command": "echo hello"})
        assert result["status"] == "passed"
        assert result["exit_code"] == 0
        assert "hello" in result["output"]

    def test_failed_exit_code(self, monkeypatch):
        """execute_suite returns 'failed' for non-zero exit code."""
        from aec.lib.runner import execute_suite

        fake_result = subprocess.CompletedProcess(
            args="false",
            returncode=1,
            stdout="",
            stderr="error occurred",
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)

        result = execute_suite(Path("/tmp"), "lint", {"command": "false"})
        assert result["status"] == "failed"
        assert result["exit_code"] == 1
        assert "error occurred" in result["output"]

    def test_measures_duration(self, monkeypatch):
        """execute_suite records duration_seconds."""
        from aec.lib.runner import execute_suite

        # Simulate a 0.5s elapsed time
        call_count = 0

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            return 100.0 if call_count == 1 else 100.5

        monkeypatch.setattr(time, "monotonic", fake_monotonic)

        fake_result = subprocess.CompletedProcess(
            args="sleep 0.5", returncode=0, stdout="", stderr=""
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)

        result = execute_suite(Path("/tmp"), "slow", {"command": "sleep 0.5"})
        assert result["duration_seconds"] == 0.5

    def test_handles_timeout(self, monkeypatch):
        """execute_suite returns failed status on timeout."""
        from aec.lib.runner import execute_suite

        def raise_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="hang", timeout=3600)

        monkeypatch.setattr(subprocess, "run", raise_timeout)

        result = execute_suite(Path("/tmp"), "hang", {"command": "hang"})
        assert result["status"] == "failed"
        assert result["exit_code"] == -1
        assert "timed out" in result["output"]

    def test_no_command_returns_failed(self):
        """execute_suite returns failed when no command is specified."""
        from aec.lib.runner import execute_suite

        result = execute_suite(Path("/tmp"), "empty", {})
        assert result["status"] == "failed"
        assert result["exit_code"] == -1
        assert "No command" in result["output"]


class TestRunCleanup:
    """Tests for run_cleanup()."""

    def test_returns_true_on_success(self, monkeypatch):
        """run_cleanup returns True when exit code is 0."""
        from aec.lib.runner import run_cleanup

        fake_result = subprocess.CompletedProcess(
            args="cleanup", returncode=0, stdout="", stderr=""
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)

        assert run_cleanup(Path("/tmp"), "cleanup") is True

    def test_returns_false_on_failure(self, monkeypatch):
        """run_cleanup returns False when exit code is non-zero."""
        from aec.lib.runner import run_cleanup

        fake_result = subprocess.CompletedProcess(
            args="cleanup", returncode=1, stdout="", stderr=""
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)

        assert run_cleanup(Path("/tmp"), "cleanup") is False

    def test_returns_false_on_timeout(self, monkeypatch):
        """run_cleanup returns False when command times out."""
        from aec.lib.runner import run_cleanup

        def raise_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="cleanup", timeout=300)

        monkeypatch.setattr(subprocess, "run", raise_timeout)

        assert run_cleanup(Path("/tmp"), "cleanup") is False


class TestCheckProjectPrerequisites:
    """Tests for check_project_prerequisites()."""

    def test_passes_when_all_available(self, monkeypatch):
        """Returns (True, []) when all prerequisites pass."""
        from aec.lib.runner import check_project_prerequisites

        monkeypatch.setattr(
            "aec.lib.prerequisites.check_prerequisites",
            lambda prereqs: (True, []),
        )

        aec_data = {
            "test": {
                "prerequisites": [{"type": "command", "value": "python3"}],
            }
        }
        passed, failures = check_project_prerequisites(aec_data)
        assert passed is True
        assert failures == []

    def test_fails_when_one_missing(self, monkeypatch):
        """Returns (False, [reason]) when a prerequisite fails."""
        from aec.lib.runner import check_project_prerequisites

        monkeypatch.setattr(
            "aec.lib.prerequisites.check_prerequisites",
            lambda prereqs: (False, ["command not found: nonexistent"]),
        )

        aec_data = {
            "test": {
                "prerequisites": [{"type": "command", "value": "nonexistent"}],
            }
        }
        passed, failures = check_project_prerequisites(aec_data)
        assert passed is False
        assert len(failures) == 1

    def test_passes_with_empty_prerequisites(self):
        """Returns (True, []) when there are no prerequisites."""
        from aec.lib.runner import check_project_prerequisites

        aec_data = {"test": {"prerequisites": []}}
        passed, failures = check_project_prerequisites(aec_data)
        assert passed is True
        assert failures == []

    def test_passes_with_no_test_section(self):
        """Returns (True, []) when test section is missing."""
        from aec.lib.runner import check_project_prerequisites

        passed, failures = check_project_prerequisites({})
        assert passed is True
        assert failures == []


class TestCheckSuitePrerequisites:
    """Tests for check_suite_prerequisites()."""

    def test_passes_with_empty_prerequisites(self):
        """Returns (True, []) when suite has no prerequisites."""
        from aec.lib.runner import check_suite_prerequisites

        passed, failures = check_suite_prerequisites({})
        assert passed is True
        assert failures == []

    def test_passes_with_explicit_empty_list(self):
        """Returns (True, []) when prerequisites is an empty list."""
        from aec.lib.runner import check_suite_prerequisites

        passed, failures = check_suite_prerequisites({"prerequisites": []})
        assert passed is True
        assert failures == []

    def test_fails_when_prerequisite_missing(self, monkeypatch):
        """Returns (False, [reason]) when a prerequisite fails."""
        from aec.lib.runner import check_suite_prerequisites

        monkeypatch.setattr(
            "aec.lib.prerequisites.check_prerequisites",
            lambda prereqs: (False, ["command not found: docker"]),
        )

        suite_config = {
            "command": "pytest",
            "prerequisites": [{"type": "command", "value": "docker"}],
        }
        passed, failures = check_suite_prerequisites(suite_config)
        assert passed is False
        assert "docker" in failures[0]


class TestRunSingleProject:
    """Tests for run_single_project()."""

    def test_skips_when_project_prerequisites_fail(self, monkeypatch):
        """Project is skipped when project-level prerequisites fail."""
        from aec.lib.runner import run_single_project

        monkeypatch.setattr(
            "aec.lib.aec_json.load_aec_json",
            lambda path: {
                "project": {"name": "test-proj"},
                "test": {
                    "prerequisites": [{"type": "command", "value": "missing-tool"}],
                    "suites": {"unit": {"command": "pytest"}},
                    "scheduled": ["unit"],
                },
                "ports": {},
            },
        )
        monkeypatch.setattr(
            "aec.lib.prerequisites.check_prerequisites",
            lambda prereqs: (False, ["command not found: missing-tool"]),
        )

        result = run_single_project(Path("/tmp/test-proj"))
        assert result["status"] == "skipped"
        assert "prerequisites" in result["reason"]

    def test_skips_suite_when_suite_prerequisites_fail(self, monkeypatch):
        """Suite is skipped when suite-level prerequisites fail."""
        from aec.lib.runner import run_single_project

        monkeypatch.setattr(
            "aec.lib.aec_json.load_aec_json",
            lambda path: {
                "project": {"name": "test-proj"},
                "test": {
                    "prerequisites": [],
                    "suites": {
                        "unit": {
                            "command": "pytest",
                            "prerequisites": [
                                {"type": "command", "value": "docker"}
                            ],
                        }
                    },
                    "scheduled": ["unit"],
                },
                "ports": {},
            },
        )

        # Project prerequisites pass, suite prerequisites fail
        call_count = 0

        def mock_check_prereqs(prereqs):
            nonlocal call_count
            call_count += 1
            if not prereqs:
                return True, []
            return False, ["command not found: docker"]

        monkeypatch.setattr(
            "aec.lib.prerequisites.check_prerequisites", mock_check_prereqs
        )
        monkeypatch.setattr(
            "aec.lib.ports.load_registry",
            lambda path: {"version": "1.0.0", "ports": {}},
        )

        result = run_single_project(Path("/tmp/test-proj"))
        assert result["suites"]["unit"]["status"] == "skipped"

    def test_runs_suites_when_prerequisites_pass(self, monkeypatch):
        """Suites execute when all prerequisites pass."""
        from aec.lib.runner import run_single_project

        monkeypatch.setattr(
            "aec.lib.aec_json.load_aec_json",
            lambda path: {
                "project": {"name": "test-proj"},
                "test": {
                    "prerequisites": [],
                    "suites": {"unit": {"command": "pytest"}},
                    "scheduled": ["unit"],
                },
                "ports": {},
            },
        )
        monkeypatch.setattr(
            "aec.lib.prerequisites.check_prerequisites",
            lambda prereqs: (True, []),
        )
        monkeypatch.setattr(
            "aec.lib.ports.load_registry",
            lambda path: {"version": "1.0.0", "ports": {}},
        )
        monkeypatch.setattr(
            "aec.lib.profiler.take_snapshot",
            lambda: {"ports": [], "processes": [], "timestamp": ""},
        )
        monkeypatch.setattr(
            "aec.lib.profiler.diff_snapshots",
            lambda before, after: {
                "new_ports": [],
                "closed_ports": [],
                "new_processes": [],
                "ended_processes": [],
            },
        )

        fake_result = subprocess.CompletedProcess(
            args="pytest", returncode=0, stdout="all passed\n", stderr=""
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)

        result = run_single_project(Path("/tmp/test-proj"))
        assert result["status"] == "passed"
        assert result["suites"]["unit"]["status"] == "passed"

    def test_skips_when_no_aec_json(self, monkeypatch):
        """Project is skipped when .aec.json does not exist."""
        from aec.lib.runner import run_single_project

        monkeypatch.setattr("aec.lib.aec_json.load_aec_json", lambda path: None)

        result = run_single_project(Path("/tmp/no-config"))
        assert result["status"] == "skipped"
        assert "no .aec.json" in result["reason"]

    def test_run_all_runs_all_suites(self, monkeypatch):
        """With run_all=True, all suites execute regardless of scheduled list."""
        from aec.lib.runner import run_single_project

        monkeypatch.setattr(
            "aec.lib.aec_json.load_aec_json",
            lambda path: {
                "project": {"name": "test-proj"},
                "test": {
                    "prerequisites": [],
                    "suites": {
                        "unit": {"command": "pytest"},
                        "lint": {"command": "flake8"},
                    },
                    "scheduled": ["unit"],  # lint not scheduled
                },
                "ports": {},
            },
        )
        monkeypatch.setattr(
            "aec.lib.prerequisites.check_prerequisites",
            lambda prereqs: (True, []),
        )
        monkeypatch.setattr(
            "aec.lib.ports.load_registry",
            lambda path: {"version": "1.0.0", "ports": {}},
        )
        monkeypatch.setattr(
            "aec.lib.profiler.take_snapshot",
            lambda: {"ports": [], "processes": [], "timestamp": ""},
        )
        monkeypatch.setattr(
            "aec.lib.profiler.diff_snapshots",
            lambda before, after: {
                "new_ports": [],
                "closed_ports": [],
                "new_processes": [],
                "ended_processes": [],
            },
        )

        fake_result = subprocess.CompletedProcess(
            args="test", returncode=0, stdout="ok\n", stderr=""
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)

        result = run_single_project(Path("/tmp/test-proj"), run_all=True)
        assert "unit" in result["suites"]
        assert "lint" in result["suites"]


def _patch_run_all_dependencies(monkeypatch):
    """Patch all external dependencies used by run_all_projects."""
    monkeypatch.setattr(
        "aec.lib.scheduler_config.load_scheduler_config",
        lambda: {
            "version": "1.0.0",
            "last_run": None,
            "retention": {"mode": "manual", "keep_days": 30},
        },
    )
    monkeypatch.setattr(
        "aec.lib.scheduler_config.save_scheduler_config", lambda cfg: None
    )
    monkeypatch.setattr(
        "aec.lib.scheduler_config.update_last_run",
        lambda cfg, stats: cfg,
    )
    monkeypatch.setattr(
        "aec.lib.prerequisites.check_prerequisites",
        lambda prereqs: (True, []),
    )
    monkeypatch.setattr(
        "aec.lib.ports.load_registry",
        lambda path: {"version": "1.0.0", "ports": {}},
    )
    monkeypatch.setattr(
        "aec.lib.profiler.take_snapshot",
        lambda: {"ports": [], "processes": [], "timestamp": ""},
    )
    monkeypatch.setattr(
        "aec.lib.profiler.diff_snapshots",
        lambda before, after: {
            "new_ports": [],
            "closed_ports": [],
            "new_processes": [],
            "ended_processes": [],
        },
    )
    monkeypatch.setattr(
        "aec.lib.profiler.save_profile", lambda data, path: None
    )
    monkeypatch.setattr(
        "aec.lib.reports.create_report_dir",
        lambda base, ts: Path("/tmp/reports") / ts,
    )
    monkeypatch.setattr(
        "aec.lib.reports.write_suite_output",
        lambda *args: Path("/tmp/reports/out.txt"),
    )
    monkeypatch.setattr(
        "aec.lib.reports.generate_summary",
        lambda *args: Path("/tmp/reports/summary.json"),
    )
    monkeypatch.setattr("aec.lib.reports.open_report", lambda path: None)
    monkeypatch.setattr("aec.lib.preferences.get_setting", lambda key: None)

    fake_result = subprocess.CompletedProcess(
        args="pytest", returncode=0, stdout="ok\n", stderr=""
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)


class TestRunAllProjects:
    """Tests for run_all_projects()."""

    def test_randomizes_order_with_recorded_seed(self, monkeypatch):
        """run_all_projects records the random seed used for shuffling."""
        from aec.lib.runner import run_all_projects
        from aec.lib.tracking import TrackedRepo

        repos = [
            TrackedRepo("2026-01-01T00:00:00Z", "2.0.0", Path("/tmp/a"), True),
            TrackedRepo("2026-01-01T00:00:00Z", "2.0.0", Path("/tmp/b"), True),
            TrackedRepo("2026-01-01T00:00:00Z", "2.0.0", Path("/tmp/c"), True),
        ]
        monkeypatch.setattr("aec.lib.tracking.list_repos", lambda: repos)

        aec_data = {
            "project": {"name": "proj"},
            "test": {
                "prerequisites": [],
                "suites": {"unit": {"command": "pytest"}},
                "scheduled": ["unit"],
            },
            "ports": {},
        }
        monkeypatch.setattr("aec.lib.aec_json.load_aec_json", lambda path: aec_data)
        _patch_run_all_dependencies(monkeypatch)

        result = run_all_projects()
        assert "seed" in result
        assert isinstance(result["seed"], int)

    def test_filters_to_projects_with_scheduled_suites(self, monkeypatch):
        """Only projects with non-empty test.scheduled are included."""
        from aec.lib.runner import run_all_projects
        from aec.lib.tracking import TrackedRepo

        repos = [
            TrackedRepo("2026-01-01T00:00:00Z", "2.0.0", Path("/tmp/with-tests"), True),
            TrackedRepo("2026-01-01T00:00:00Z", "2.0.0", Path("/tmp/no-tests"), True),
        ]
        monkeypatch.setattr("aec.lib.tracking.list_repos", lambda: repos)

        def mock_load_aec(path):
            if "with-tests" in str(path):
                return {
                    "project": {"name": "with-tests"},
                    "test": {
                        "prerequisites": [],
                        "suites": {"unit": {"command": "pytest"}},
                        "scheduled": ["unit"],
                    },
                    "ports": {},
                }
            return {
                "project": {"name": "no-tests"},
                "test": {"prerequisites": [], "suites": {}, "scheduled": []},
                "ports": {},
            }

        monkeypatch.setattr("aec.lib.aec_json.load_aec_json", mock_load_aec)
        _patch_run_all_dependencies(monkeypatch)

        result = run_all_projects()
        assert result["total_projects"] == 1
        assert "/tmp/with-tests" in str(list(result["projects"].keys()))


class TestAnalyzePortObservations:
    """Tests for analyze_port_observations()."""

    def test_detects_unregistered_ports(self):
        """Unregistered ports appear as observations."""
        from aec.lib.runner import analyze_port_observations

        diff = {"new_ports": [8080, 3000]}
        registry = {"version": "1.0.0", "ports": {"3000": {"port": 3000, "project": "web"}}}

        observations = analyze_port_observations("my-proj", diff, registry, True)
        assert len(observations) == 1
        assert observations[0]["port"] == 8080
        assert observations[0]["type"] == "unregistered_port"

    def test_no_observations_when_disabled(self):
        """No observations when port management is disabled."""
        from aec.lib.runner import analyze_port_observations

        diff = {"new_ports": [8080]}
        registry = {"version": "1.0.0", "ports": {}}

        observations = analyze_port_observations("my-proj", diff, registry, False)
        assert observations == []

    def test_no_observations_when_all_registered(self):
        """No observations when all ports are registered."""
        from aec.lib.runner import analyze_port_observations

        diff = {"new_ports": [3000]}
        registry = {"version": "1.0.0", "ports": {"3000": {"port": 3000, "project": "web"}}}

        observations = analyze_port_observations("my-proj", diff, registry, True)
        assert observations == []


class TestAnalyzeProcessObservations:
    """Tests for analyze_process_observations()."""

    def test_detects_leaked_processes(self):
        """Leaked processes appear as observations."""
        from aec.lib.runner import analyze_process_observations

        diff = {
            "new_processes": [
                {"pid": 1234, "name": "node"},
                {"pid": 5678, "name": "python"},
            ]
        }

        observations = analyze_process_observations("my-proj", "unit", diff)
        assert len(observations) == 2
        assert observations[0]["type"] == "leaked_process"
        assert observations[0]["suite"] == "unit"

    def test_no_leaks_when_clean(self):
        """No observations when no processes leaked."""
        from aec.lib.runner import analyze_process_observations

        diff = {"new_processes": []}

        observations = analyze_process_observations("my-proj", "unit", diff)
        assert observations == []


class TestApplyRetention:
    """Tests for apply_retention()."""

    def test_calls_prune_when_auto(self, monkeypatch):
        """Prune functions are called when retention mode is 'auto'."""
        from aec.lib.runner import apply_retention

        prune_reports_calls = []
        prune_profiles_calls = []

        monkeypatch.setattr(
            "aec.lib.reports.prune_old_reports",
            lambda base, keep: prune_reports_calls.append((base, keep)) or 0,
        )
        monkeypatch.setattr(
            "aec.lib.reports.prune_old_profiles",
            lambda base, keep: prune_profiles_calls.append((base, keep)) or 0,
        )

        config = {"retention": {"mode": "auto", "keep_days": 14}}
        apply_retention(config)

        assert len(prune_reports_calls) == 1
        assert prune_reports_calls[0][1] == 14
        assert len(prune_profiles_calls) == 1
        assert prune_profiles_calls[0][1] == 14

    def test_does_nothing_when_manual(self, monkeypatch):
        """Prune functions are NOT called when retention mode is 'manual'."""
        from aec.lib.runner import apply_retention

        prune_calls = []

        monkeypatch.setattr(
            "aec.lib.reports.prune_old_reports",
            lambda base, keep: prune_calls.append("reports") or 0,
        )
        monkeypatch.setattr(
            "aec.lib.reports.prune_old_profiles",
            lambda base, keep: prune_calls.append("profiles") or 0,
        )

        config = {"retention": {"mode": "manual", "keep_days": 30}}
        apply_retention(config)

        assert prune_calls == []
