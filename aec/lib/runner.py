"""AEC test runner — executes test suites, profiles, and generates reports."""

import logging
import random
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


def execute_suite(project_dir: Path, suite_name: str, suite_config: dict) -> dict:
    """Execute a single test suite.

    Runs the suite's command via subprocess, captures output, exit code,
    and duration.

    Args:
        project_dir: Working directory for the command.
        suite_name: Name of the suite (for logging).
        suite_config: Dict with at least a "command" key.

    Returns:
        Dict with status, exit_code, duration_seconds, and output.
    """
    command = suite_config.get("command", "")
    if not command:
        return {
            "status": "failed",
            "exit_code": -1,
            "duration_seconds": 0.0,
            "output": "No command specified for suite",
        }

    start = time.monotonic()
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=3600,
        )
        duration = time.monotonic() - start
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr if output else result.stderr
        return {
            "status": "passed" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "duration_seconds": round(duration, 3),
            "output": output,
        }
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - start
        return {
            "status": "failed",
            "exit_code": -1,
            "duration_seconds": round(duration, 3),
            "output": f"Suite '{suite_name}' timed out after 3600 seconds",
        }


def run_cleanup(project_dir: Path, cleanup_command: str) -> bool:
    """Run a cleanup command after a test suite.

    Args:
        project_dir: Working directory for the command.
        cleanup_command: Shell command to execute.

    Returns:
        True if the command exited with code 0, False otherwise.
    """
    try:
        result = subprocess.run(
            cleanup_command,
            shell=True,
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def check_project_prerequisites(aec_data: dict) -> Tuple[bool, List[str]]:
    """Check project-level prerequisites from aec_data.

    Args:
        aec_data: Loaded .aec.json data.

    Returns:
        (all_passed, list_of_failure_reasons).
    """
    from aec.lib.prerequisites import check_prerequisites

    prereqs = aec_data.get("test", {}).get("prerequisites", [])
    if not prereqs:
        return True, []
    results = check_prerequisites(prereqs)
    failures = [f"{name}: {detail}" for name, available, detail in results if not available]
    return len(failures) == 0, failures


def check_suite_prerequisites(suite_config: dict) -> Tuple[bool, List[str]]:
    """Check suite-level prerequisites.

    Args:
        suite_config: Suite configuration dict.

    Returns:
        (all_passed, list_of_failure_reasons).
    """
    from aec.lib.prerequisites import check_prerequisites

    prereqs = suite_config.get("prerequisites", [])
    if not prereqs:
        return True, []
    results = check_prerequisites(prereqs)
    failures = [f"{name}: {detail}" for name, available, detail in results if not available]
    return len(failures) == 0, failures


def analyze_port_observations(
    project_name: str,
    profile_diff: dict,
    port_registry: dict,
    port_mgmt_enabled: bool,
) -> list:
    """Compare observed ports against the port registry.

    Args:
        project_name: Name of the project being tested.
        profile_diff: Diff from profiler.diff_snapshots().
        port_registry: Loaded port registry dict.
        port_mgmt_enabled: Whether port management is enabled.

    Returns:
        List of observation dicts with type, port, and message.
    """
    if not port_mgmt_enabled:
        return []

    observations = []
    registered_ports = set()
    for _key, entry in port_registry.get("ports", {}).items():
        if isinstance(entry, dict) and "port" in entry:
            registered_ports.add(entry["port"])
        else:
            # key might be the port number itself
            try:
                registered_ports.add(int(_key))
            except (ValueError, TypeError):
                pass

    for port_info in profile_diff.get("new_ports", []):
        port = port_info if isinstance(port_info, int) else port_info.get("port", 0)
        if port and port not in registered_ports:
            observations.append({
                "type": "unregistered_port",
                "port": port,
                "project": project_name,
                "message": f"Port {port} opened but not in registry",
            })

    return observations


def analyze_process_observations(
    project_name: str,
    suite_name: str,
    profile_diff: dict,
) -> list:
    """Check for process leaks after a suite run.

    Args:
        project_name: Name of the project.
        suite_name: Name of the suite.
        profile_diff: Diff from profiler.diff_snapshots().

    Returns:
        List of observation dicts with type, process info, and message.
    """
    observations = []
    for proc in profile_diff.get("new_processes", []):
        observations.append({
            "type": "leaked_process",
            "project": project_name,
            "suite": suite_name,
            "process": proc,
            "message": f"Process still running after suite '{suite_name}' completed",
        })
    return observations


def run_single_project(project_dir: Path, run_all: bool = False) -> dict:
    """Run test suites for a single project.

    Args:
        project_dir: Path to the project directory.
        run_all: If True, run ALL suites. If False, run only scheduled suites.

    Returns:
        Results dict with per-suite results and profiles.
    """
    from aec.lib.aec_json import load_aec_json
    from aec.lib.config import AEC_PORTS_REGISTRY
    from aec.lib.ports import load_registry
    from aec.lib.profiler import diff_snapshots, take_snapshot

    aec_data = load_aec_json(project_dir)
    if aec_data is None:
        return {
            "project": str(project_dir),
            "status": "skipped",
            "reason": "no .aec.json found",
            "suites": {},
        }

    project_name = aec_data.get("project", {}).get("name", project_dir.name)

    # Check project-level prerequisites
    prereqs_ok, failures = check_project_prerequisites(aec_data)
    if not prereqs_ok:
        return {
            "project": project_name,
            "status": "skipped",
            "reason": f"prerequisites failed: {', '.join(failures)}",
            "suites": {},
        }

    test_config = aec_data.get("test", {})
    all_suites = test_config.get("suites", {})
    scheduled = test_config.get("scheduled", [])

    if run_all:
        suites_to_run = all_suites
    else:
        suites_to_run = {
            name: cfg for name, cfg in all_suites.items() if name in scheduled
        }

    if not suites_to_run:
        return {
            "project": project_name,
            "status": "skipped",
            "reason": "no suites to run",
            "suites": {},
        }

    # Load port registry for observations
    port_registry = load_registry(AEC_PORTS_REGISTRY)
    port_mgmt_enabled = bool(aec_data.get("ports", {}))

    suite_results = {}
    profiles = {}
    observations = []

    for suite_name, suite_config in suites_to_run.items():
        # Check suite-level prerequisites
        suite_ok, suite_failures = check_suite_prerequisites(suite_config)
        if not suite_ok:
            suite_results[suite_name] = {
                "status": "skipped",
                "reason": f"prerequisites failed: {', '.join(suite_failures)}",
            }
            continue

        # Take pre-snapshot
        before = take_snapshot()

        # Execute the suite
        result = execute_suite(project_dir, suite_name, suite_config)
        suite_results[suite_name] = result

        # Take post-snapshot and diff
        after = take_snapshot()
        diff = diff_snapshots(before, after)
        profiles[suite_name] = diff

        # Run cleanup if specified
        cleanup_cmd = suite_config.get("cleanup")
        if cleanup_cmd:
            run_cleanup(project_dir, cleanup_cmd)

        # Analyze observations
        port_obs = analyze_port_observations(
            project_name, diff, port_registry, port_mgmt_enabled
        )
        proc_obs = analyze_process_observations(project_name, suite_name, diff)
        observations.extend(port_obs)
        observations.extend(proc_obs)

    # Determine overall status
    statuses = [r.get("status") for r in suite_results.values()]
    if all(s == "passed" for s in statuses):
        overall = "passed"
    elif all(s == "skipped" for s in statuses):
        overall = "skipped"
    else:
        overall = "failed"

    return {
        "project": project_name,
        "status": overall,
        "suites": suite_results,
        "profiles": profiles,
        "observations": observations,
    }


def apply_retention(config: dict) -> None:
    """Apply retention policy based on scheduler config.

    If retention mode is "auto", prunes old reports and profiles.

    Args:
        config: Scheduler config dict.
    """
    from aec.lib.config import AEC_HOME
    from aec.lib.reports import prune_old_profiles, prune_old_reports
    from aec.lib.scheduler_config import get_retention_config

    retention = get_retention_config(config)
    if retention.get("mode") != "auto":
        return

    keep_days = retention.get("keep_days", 30)
    reports_dir = AEC_HOME / "reports"
    profiles_dir = AEC_HOME / "profiles"

    prune_old_reports(reports_dir, keep_days)
    prune_old_profiles(profiles_dir, keep_days)


def run_all_projects(global_mode: bool = True) -> dict:
    """Run scheduled test suites across all tracked projects.

    Args:
        global_mode: If True, operates on all tracked repos.

    Returns:
        Overall results dict with per-project results.
    """
    from aec.lib.aec_json import load_aec_json
    from aec.lib.config import AEC_HOME
    from aec.lib.profiler import save_profile
    from aec.lib.reports import (
        create_report_dir,
        generate_summary,
        open_report,
        write_suite_output,
    )
    from aec.lib.scheduler_config import (
        load_scheduler_config,
        save_scheduler_config,
        update_last_run,
    )
    from aec.lib.tracking import list_repos

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sched_config = load_scheduler_config()

    # Get tracked repos that exist on disk
    repos = [r for r in list_repos() if r.exists]

    # Filter to projects that have .aec.json with non-empty test.scheduled
    eligible = []
    for repo in repos:
        aec_data = load_aec_json(repo.path)
        if aec_data is None:
            continue
        scheduled = aec_data.get("test", {}).get("scheduled", [])
        if scheduled:
            eligible.append(repo)

    # Randomize order with recorded seed
    seed = random.randint(0, 2**31 - 1)
    random.seed(seed)
    random.shuffle(eligible)

    project_results = {}
    total_passed = 0
    total_failed = 0
    total_skipped = 0

    for repo in eligible:
        result = run_single_project(repo.path, run_all=False)
        project_results[str(repo.path)] = result

        status = result.get("status", "skipped")
        if status == "passed":
            total_passed += 1
        elif status == "failed":
            total_failed += 1
        else:
            total_skipped += 1

    # Generate reports
    reports_dir = AEC_HOME / "reports"
    report_dir = create_report_dir(reports_dir, timestamp.replace(":", "-"))

    for project_path, result in project_results.items():
        project_name = result.get("project", Path(project_path).name)
        for suite_name, suite_result in result.get("suites", {}).items():
            output = suite_result.get("output", "")
            write_suite_output(report_dir, project_name, suite_name, output)

    overall_results = {
        "timestamp": timestamp,
        "seed": seed,
        "total_projects": len(eligible),
        "passed": total_passed,
        "failed": total_failed,
        "skipped": total_skipped,
        "projects": project_results,
    }

    summary_path = generate_summary(report_dir, overall_results)

    # Save profiles
    profiles_dir = AEC_HOME / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    all_profiles = {}
    for project_path, result in project_results.items():
        profiles = result.get("profiles", {})
        if profiles:
            all_profiles[result.get("project", Path(project_path).name)] = profiles
    if all_profiles:
        profile_path = profiles_dir / f"{timestamp.replace(':', '-')}.json"
        save_profile(all_profiles, profile_path)

    # Update scheduler config
    stats = {
        "total_projects": len(eligible),
        "passed": total_passed,
        "failed": total_failed,
        "skipped": total_skipped,
    }
    sched_config = update_last_run(sched_config, stats)
    save_scheduler_config(sched_config)

    # Apply retention
    apply_retention(sched_config)

    # Open report if configured
    try:
        from aec.lib.preferences import get_setting

        viewer = get_setting("report_viewer")
        if viewer:
            open_report(summary_path)
    except Exception:
        pass

    return overall_results
