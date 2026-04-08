"""Scheduler configuration management for AEC quality infrastructure.

CRUD operations for ~/.agents-environment-config/scheduler-config.json.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

SCHEDULER_CONFIG_VERSION = "1.0.0"


def create_default_config() -> dict:
    """Return a new default scheduler config dict."""
    return {
        "version": SCHEDULER_CONFIG_VERSION,
        "schedule": {
            "enabled": True,
            "time": "02:00",
            "timezone": "local",
        },
        "execution": {
            "mode": "sequential",
            "randomize_order": True,
            "parallel_enabled": False,
            "parallelization_plan": None,
            "min_profile_runs_for_parallel": 3,
        },
        "retention": {
            "report_mode": "auto",
            "report_days": 30,
            "profile_days": 90,
        },
        "last_run": None,
    }


def load_scheduler_config(config_path: Path) -> dict:
    """Load scheduler-config.json. Return default if missing/corrupt.

    Uses setdefault to ensure all required keys exist for forward compatibility.
    """
    defaults = create_default_config()

    if not config_path.exists():
        return defaults

    try:
        loaded = json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError):
        return defaults

    # Top-level setdefault for forward compatibility
    for key, value in defaults.items():
            loaded.setdefault(key, value)

    # Nested setdefault for sub-dicts
    for section in ("schedule", "execution", "retention"):
        if isinstance(loaded.get(section), dict) and isinstance(defaults.get(section), dict):
            for k, v in defaults[section].items():
                loaded[section].setdefault(k, v)

    return loaded


def save_scheduler_config(config: dict, config_path: Path) -> None:
    """Write config to disk as JSON with indent=2. Creates parent dirs."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n")


def update_last_run(
    config: dict,
    projects_run: int,
    suites_passed: int,
    suites_failed: int,
    suites_skipped: int,
    seed: int,
) -> dict:
    """Update the last_run section with current timestamp and stats.

    Returns the updated config.
    """
    config["last_run"] = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "projects_run": projects_run,
        "suites_passed": suites_passed,
        "suites_failed": suites_failed,
        "suites_skipped": suites_skipped,
        "seed": seed,
    }
    return config


def update_parallelization_plan(
    config: dict, lanes: list[list[str]], based_on_runs: int
) -> dict:
    """Set the parallelization_plan with computed_at timestamp, lanes, and based_on_runs.

    Returns the updated config.
    """
    config["execution"]["parallelization_plan"] = {
        "computed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lanes": lanes,
        "based_on_runs": based_on_runs,
    }
    return config


def get_schedule_time(config: dict) -> tuple[int, int]:
    """Parse schedule.time (e.g., '02:00') into (hour, minute) tuple."""
    time_str = config["schedule"]["time"]
    parts = time_str.split(":")
    return (int(parts[0]), int(parts[1]))


def is_schedule_enabled(config: dict) -> bool:
    """Check if schedule.enabled is True."""
    return config["schedule"]["enabled"] is True


def get_retention_config(config: dict) -> dict:
    """Return the retention section dict."""
    return config["retention"]


def get_execution_config(config: dict) -> dict:
    """Return the execution section dict."""
    return config["execution"]
