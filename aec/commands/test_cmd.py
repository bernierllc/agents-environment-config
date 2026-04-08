"""CLI command handlers for `aec test` subcommands."""

import sys
from pathlib import Path

from ..lib.console import Console


def run_test_run(global_flag: bool = False) -> None:
    """Run test suites for one or all tracked projects."""
    from ..lib.runner import run_single_project, run_all_projects

    if global_flag:
        Console.info("Running tests for all tracked projects...")
        exit_code = run_all_projects(global_mode=True)
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
        exit_code = run_single_project(repo, run_all=True)

    if exit_code == 0:
        Console.success("All tests passed.")
    else:
        Console.error(f"Some tests failed (exit code {exit_code}).")


def run_test_schedule() -> None:
    """Interactive schedule setup for daily test runs."""
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

    config = load_scheduler_config()
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
    save_scheduler_config(config)

    # 6. Register with OS scheduler
    scheduler = get_scheduler()
    runner_path = str(Path(sys.executable).parent / "aec")
    scheduler.register(runner_path, schedule["time"])

    Console.success(f"Scheduled test runs enabled at {schedule['time']} daily")


def run_test_status(global_flag: bool = False) -> None:
    """Show test configuration or global schedule status."""
    if global_flag:
        from ..lib.scheduler_config import (
            load_scheduler_config,
            is_schedule_enabled,
            get_schedule_time,
        )
        from ..lib.schedulers import get_scheduler
        from ..lib.tracking import list_repos

        config = load_scheduler_config()
        enabled = is_schedule_enabled(config)
        time = get_schedule_time(config)
        scheduler = get_scheduler()

        Console.subheader("Scheduled Test Status")
        Console.print(f"  Enabled:       {'yes' if enabled else 'no'}")
        Console.print(f"  Run time:      {time}")
        Console.print(f"  Last run:      {scheduler.last_run() or 'never'}")
        Console.print(f"  Next run:      {scheduler.next_run() or 'not scheduled'}")
        Console.print(f"  Parallel mode: {'yes' if config.get('parallel') else 'no'}")

        repos = list_repos()
        Console.print(f"  Tracked projects: {len(repos)}")
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
    from ..lib.scheduler_config import load_scheduler_config, save_scheduler_config
    from ..lib.schedulers import get_scheduler

    config = load_scheduler_config()
    schedule = config.setdefault("schedule", {})
    time = schedule.get("time", "02:00")

    scheduler = get_scheduler()
    runner_path = str(Path(sys.executable).parent / "aec")
    scheduler.register(runner_path, time)

    schedule["enabled"] = True
    save_scheduler_config(config)
    Console.success(f"Scheduled test runs enabled at {time} daily")


def run_test_disable() -> None:
    """Disable scheduled test runs."""
    from ..lib.scheduler_config import load_scheduler_config, save_scheduler_config
    from ..lib.schedulers import get_scheduler

    config = load_scheduler_config()
    scheduler = get_scheduler()
    scheduler.unregister()

    config.setdefault("schedule", {})["enabled"] = False
    save_scheduler_config(config)
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


def run_test_detect() -> None:
    """Re-run test framework detection for the current project."""
    from ..lib.scope import find_tracked_repo
    from ..lib.test_detection import detect_test_frameworks, scan_test_scripts
    from ..lib.aec_json import load_aec_json, save_aec_json, update_test_section

    repo = find_tracked_repo()
    if repo is None:
        Console.error("Not inside a tracked project.")
        return

    Console.info(f"Detecting test frameworks in {repo.name}...")

    frameworks = detect_test_frameworks(repo)
    scripts = scan_test_scripts(repo)

    if not frameworks and not scripts:
        Console.info("No test frameworks or scripts detected.")
        return

    # Present findings
    if frameworks:
        Console.subheader("Detected frameworks")
        for fw in frameworks:
            Console.print(f"  {fw.get('name', 'unknown')}: {fw.get('command', '(no command)')}")

    if scripts:
        Console.subheader("Detected test scripts")
        for script in scripts:
            Console.print(f"  {script.get('name', 'unknown')}: {script.get('command', '')}")

    # Build suites from detections
    suites = {}
    for fw in frameworks:
        name = fw.get("name", "unknown")
        suites[name] = {
            "command": fw.get("command", ""),
            "framework": name,
        }
    for script in scripts:
        name = script.get("name", "unknown")
        if name not in suites:
            suites[name] = {
                "command": script.get("command", ""),
            }

    # Update .aec.json
    data = load_aec_json(repo) or {}
    update_test_section(data, suites=suites)
    save_aec_json(repo, data)

    Console.success("Updated test configuration")
