"""CLI command handlers for `aec test` subcommands."""

import sys
from pathlib import Path

from ..lib.console import Console

from .test_detect_impl import run_test_detect


def _print_results(result: dict) -> None:
    """Format and print test results to terminal."""
    project_name = result.get("project", "unknown")
    Console.subheader(project_name)

    for suite_name, suite_result in result.get("suites", {}).items():
        status = suite_result.get("status", "unknown")
        duration = suite_result.get("duration_seconds")
        dur_str = f"{duration:6.1f}s" if duration is not None else "      "

        if status == "passed":
            Console.success(f"{suite_name:<25} {dur_str}   passed")
        elif status == "skipped":
            reason = suite_result.get("reason", "")
            Console.info(f"{suite_name:<25}          skipped ({reason})")
        else:
            exit_code = suite_result.get("exit_code", 1)
            Console.error(f"{suite_name:<25} {dur_str}   FAILED (exit {exit_code})")

    observations = result.get("observations", [])
    if observations:
        Console.print()
        for obs in observations:
            Console.warning(obs.get("message", str(obs)))


def run_test_run(global_flag: bool = False) -> None:
    """Run test suites for one or all tracked projects."""
    from ..lib.runner import run_single_project, run_all_projects, write_reports
    from datetime import datetime, timezone

    if global_flag:
        Console.info("Running tests for all tracked projects...")
        results = run_all_projects(global_mode=True)
        Console.print()
        for project_path, result in results.get("projects", {}).items():
            _print_results(result)
        Console.print()
        passed = results.get("passed", 0)
        failed = results.get("failed", 0)
        skipped = results.get("skipped", 0)
        Console.print(f"Projects: {passed} passed, {failed} failed, {skipped} skipped")
        if results.get("summary_path"):
            Console.info(f"Report: {results['summary_path']}")
    else:
        from ..lib.scope import find_tracked_repo

        repo = find_tracked_repo()
        if repo is None:
            Console.error(
                "Not inside a tracked project. "
                "Use --global to run all projects, or run from a tracked repo."
            )
            return
        Console.info(f"Running tests for {repo.name}...")
        result = run_single_project(repo, run_all=True)

        # Write reports for local runs too
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        project_name = result.get("project", repo.name)
        summary_path = write_reports(
            {str(repo): result}, timestamp, seed=0,
            execution_order=[project_name],
        )

        Console.print()
        _print_results(result)
        Console.print()

        statuses = [s.get("status") for s in result.get("suites", {}).values()]
        passed = sum(1 for s in statuses if s == "passed")
        failed = sum(1 for s in statuses if s == "failed")
        skipped = sum(1 for s in statuses if s == "skipped")
        Console.print(f"Suites: {passed} passed, {failed} failed, {skipped} skipped")
        Console.info(f"Report: {summary_path}")


def run_test_schedule(global_flag: bool = False) -> None:
    """Configure scheduled tests: repo ``.aec.json`` or global OS time with ``-g``."""
    if global_flag:
        _run_test_schedule_global()
        return

    from ..lib.scope import find_tracked_repo
    from ..lib.test_schedule_repo import run_repo_schedule_interactive

    repo = find_tracked_repo()
    if repo is not None:
        run_repo_schedule_interactive(repo)
        return

    _run_test_schedule_global()


def _run_test_schedule_global() -> None:
    """Interactive setup for the machine-wide daily test job (scheduler-config + OS)."""
    from ..lib.config import AEC_SCHEDULER_CONFIG
    from ..lib.preferences import get_preference, set_preference
    from ..lib.scheduler_config import (
        load_scheduler_config,
        save_scheduler_config,
    )
    from ..lib.schedulers import get_scheduler

    # 1. Check scheduled_tests_enabled preference
    enabled_pref = get_preference("scheduled_tests_enabled")
    if not enabled_pref:
        try:
            answer = input("Scheduled tests are not enabled. Enable? [Y/n]: ")
        except EOFError:
            answer = ""
        if answer.strip().lower() in ("n", "no"):
            Console.info("Aborted.")
            return
        set_preference("scheduled_tests_enabled", True)

    config = load_scheduler_config(AEC_SCHEDULER_CONFIG)
    schedule = config.setdefault("schedule", {})

    # 2. Prompt for run time
    current_time = schedule.get("time", "02:00")
    try:
        new_time = input(f"Run time (24h format, e.g. 02:00) [{current_time}]: ")
    except EOFError:
        new_time = ""
    if not new_time.strip():
        new_time = current_time
    schedule["time"] = new_time.strip()

    # 3. Retention settings
    retention = schedule.get("retention_days", 30)
    Console.info(f"Current report retention: {retention} days")
    try:
        new_ret = input(f"Report retention days [{retention}]: ")
    except EOFError:
        new_ret = ""
    if new_ret.strip():
        try:
            schedule["retention_days"] = int(new_ret.strip())
        except ValueError:
            Console.warning("Invalid number, keeping current value.")

    # 4. Profile retention
    profile_ret = schedule.get("profile_retention_days", 90)
    Console.info(f"Current profile retention: {profile_ret} days")
    try:
        new_prof = input(f"Profile retention days [{profile_ret}]: ")
    except EOFError:
        new_prof = ""
    if new_prof.strip():
        try:
            schedule["profile_retention_days"] = int(new_prof.strip())
        except ValueError:
            Console.warning("Invalid number, keeping current value.")

    # 5. Save config
    schedule["enabled"] = True
    save_scheduler_config(config, AEC_SCHEDULER_CONFIG)

    # 6. Ensure OS scheduler entrypoint exists, then register
    from ..lib.runner_script_install import ensure_runner_script
    from ..lib.scheduler_config import get_schedule_time

    runner_path = ensure_runner_script()
    scheduler = get_scheduler()
    hour, minute = get_schedule_time(config)
    msg = scheduler.register(runner_path, hour, minute)
    Console.info(msg)

    Console.success(f"Scheduled test runs enabled at {hour:02d}:{minute:02d} daily")


def run_test_status(global_flag: bool = False) -> None:
    """Show test configuration or global schedule status."""
    if global_flag:
        from ..lib.config import AEC_SCHEDULER_CONFIG
        from ..lib.scheduler_config import (
            load_scheduler_config,
            is_schedule_enabled,
            get_schedule_time,
        )
        from ..lib.schedulers import get_scheduler
        from ..lib.tracking import list_repos

        config = load_scheduler_config(AEC_SCHEDULER_CONFIG)
        enabled = is_schedule_enabled(config)
        hour, minute = get_schedule_time(config)
        scheduler = get_scheduler()

        Console.subheader("AEC Test Schedule")
        Console.print(f"  Status:        {'enabled' if enabled else 'disabled'}")
        Console.print(f"  Time:          {hour:02d}:{minute:02d} daily")
        next_run = scheduler.get_next_run()
        Console.print(f"  Next run:      {next_run or 'not registered'}")
        last_run = config.get("last_run")
        if last_run:
            Console.print(f"  Last run:      {last_run.get('timestamp', 'unknown')}")
            Console.print(f"    Projects: {last_run.get('projects_run', 0)}, "
                         f"Passed: {last_run.get('suites_passed', 0)}, "
                         f"Failed: {last_run.get('suites_failed', 0)}")
        else:
            Console.print(f"  Last run:      never")

        parallel = config.get("execution", {}).get("parallel_enabled", False)
        Console.print(f"  Parallel:      {'enabled' if parallel else 'disabled'}")

        repos = list_repos()
        Console.print(f"  Projects:      {len(repos)} tracked")
    else:
        from ..lib.scope import find_tracked_repo
        from ..lib.aec_json import load_aec_json

        repo = find_tracked_repo()
        if repo is None:
            Console.warning(
                "Not inside a tracked project. Use --global for schedule status."
            )
            return

        data = load_aec_json(repo)
        if data is None:
            Console.info(f"No .aec.json found in {repo.name}. Run 'aec test detect' first.")
            return

        tests = data.get("test") or {}
        suites = tests.get("suites") or {}
        prereqs = tests.get("prerequisites") or []

        Console.subheader(f"Test Config: {repo.name}")
        if suites:
            for name, suite in suites.items():
                Console.print(f"  {name}: {suite.get('command', '(no command)')}")
        else:
            Console.info("  No test suites configured.")

        if prereqs:
            Console.print(f"  Prerequisites: {', '.join(prereqs)}")

        scheduled = tests.get("scheduled", False)
        Console.print(f"  Scheduled: {'yes' if scheduled else 'no'}")

        last_result = tests.get("last_run")
        if last_result:
            Console.print(f"  Last run: {last_result}")


def run_test_enable() -> None:
    """Enable scheduled test runs."""
    from ..lib.config import AEC_SCHEDULER_CONFIG
    from ..lib.scheduler_config import load_scheduler_config, save_scheduler_config, get_schedule_time
    from ..lib.schedulers import get_scheduler

    config = load_scheduler_config(AEC_SCHEDULER_CONFIG)
    hour, minute = get_schedule_time(config)

    from ..lib.runner_script_install import ensure_runner_script

    runner_path = ensure_runner_script()
    scheduler = get_scheduler()
    msg = scheduler.register(runner_path, hour, minute)
    Console.info(msg)

    config.setdefault("schedule", {})["enabled"] = True
    save_scheduler_config(config, AEC_SCHEDULER_CONFIG)
    Console.success(f"Scheduled test runs enabled at {hour:02d}:{minute:02d} daily")


def run_test_disable() -> None:
    """Disable scheduled test runs."""
    from ..lib.config import AEC_SCHEDULER_CONFIG
    from ..lib.scheduler_config import load_scheduler_config, save_scheduler_config
    from ..lib.schedulers import get_scheduler

    config = load_scheduler_config(AEC_SCHEDULER_CONFIG)
    scheduler = get_scheduler()
    msg = scheduler.unregister()
    Console.info(msg)

    config.setdefault("schedule", {})["enabled"] = False
    save_scheduler_config(config, AEC_SCHEDULER_CONFIG)
    Console.success("Scheduled test runs disabled")


def run_test_report(global_flag: bool = False) -> None:
    """View test reports."""
    from ..lib.config import AEC_HOME

    tests_dir = AEC_HOME / "tests"
    if not tests_dir.is_dir():
        Console.info("No test reports found. Run 'aec test run' first.")
        return

    # Find latest report directory (sorted by name, newest last)
    report_dirs = sorted(
        [d for d in tests_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )
    if not report_dirs:
        Console.info("No test reports found. Run 'aec test run' first.")
        return

    latest = report_dirs[-1]

    if global_flag:
        summary = latest / "summary.txt"
        if summary.exists():
            Console.subheader(f"Report: {latest.name}")
            Console.print(summary.read_text(encoding="utf-8"))
        else:
            Console.info(f"No summary found in {latest.name}")
            # List available files
            for f in sorted(latest.iterdir()):
                Console.print(f"  {f.name}")
    else:
        from ..lib.scope import find_tracked_repo

        repo = find_tracked_repo()
        if repo is None:
            Console.warning("Not inside a tracked project. Use --global for full report.")
            return

        # Look for this project's output
        project_file = latest / f"{repo.name}.txt"
        if project_file.exists():
            Console.subheader(f"Report: {repo.name} ({latest.name})")
            Console.print(project_file.read_text(encoding="utf-8"))
        else:
            Console.info(f"No report for {repo.name} in {latest.name}")
