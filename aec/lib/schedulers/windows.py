"""Windows Task Scheduler wrapper for AEC test runner."""

import subprocess
from pathlib import Path
from typing import Optional

TASK_NAME = "AEC_TestRunner"


def register(runner_path: Path, hour: int, minute: int) -> str:
    """Register the test runner with Windows Task Scheduler."""
    try:
        subprocess.run(
            [
                "schtasks",
                "/Create",
                "/SC",
                "DAILY",
                "/TN",
                TASK_NAME,
                "/TR",
                f"python {runner_path}",
                "/ST",
                f"{hour:02d}:{minute:02d}",
                "/F",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return f"Registered with Task Scheduler at {hour:02d}:{minute:02d}"
    except Exception as e:
        return f"Failed to register with Task Scheduler: {e}"


def unregister() -> str:
    """Unregister the test runner from Windows Task Scheduler."""
    try:
        subprocess.run(
            ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "Unregistered from Task Scheduler"
    except Exception as e:
        return f"Failed to unregister from Task Scheduler: {e}"


def is_registered() -> bool:
    """Check if the test runner is registered with Task Scheduler."""
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", TASK_NAME],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_next_run() -> Optional[str]:
    """Get the next scheduled run time, or None if not registered."""
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        for line in result.stdout.splitlines():
            if "Next Run Time:" in line:
                time_str = line.split(":", 1)[1].strip()
                if time_str and time_str != "N/A":
                    return time_str
    except Exception:
        pass
    return None
