"""Linux crontab scheduler wrapper for AEC test runner."""

import subprocess
from pathlib import Path
from typing import Optional

CRON_COMMENT = "# AEC test runner"


def register(runner_path: Path, hour: int, minute: int) -> str:
    """Register the test runner with crontab."""
    try:
        # Read current crontab
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        existing = result.stdout if result.returncode == 0 else ""

        # Remove any existing AEC entry
        lines = [
            line
            for line in existing.splitlines()
            if CRON_COMMENT not in line
        ]

        # Add new entry
        entry = f"{minute} {hour} * * * python3 {runner_path} {CRON_COMMENT}"
        lines.append(entry)

        new_crontab = "\n".join(lines) + "\n"
        subprocess.run(
            ["crontab", "-"],
            input=new_crontab,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return f"Registered with crontab at {hour:02d}:{minute:02d}"
    except Exception as e:
        return f"Failed to register with crontab: {e}"


def unregister() -> str:
    """Unregister the test runner from crontab."""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return "Unregistered from crontab"

        lines = [
            line
            for line in result.stdout.splitlines()
            if CRON_COMMENT not in line
        ]

        new_crontab = "\n".join(lines) + "\n" if lines else ""
        subprocess.run(
            ["crontab", "-"],
            input=new_crontab,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "Unregistered from crontab"
    except Exception as e:
        return f"Failed to unregister from crontab: {e}"


def is_registered() -> bool:
    """Check if the test runner is registered in crontab."""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return CRON_COMMENT in result.stdout
    except Exception:
        return False


def get_next_run() -> Optional[str]:
    """Get the next scheduled run time, or None if not registered."""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        for line in result.stdout.splitlines():
            if CRON_COMMENT in line:
                parts = line.split()
                if len(parts) >= 2:
                    minute = int(parts[0])
                    hour = int(parts[1])
                    return f"{hour:02d}:{minute:02d} daily"
    except Exception:
        pass
    return None
