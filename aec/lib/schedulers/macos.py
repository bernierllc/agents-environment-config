"""macOS launchd scheduler wrapper for AEC test runner."""

import subprocess
from pathlib import Path
from typing import Optional

PLIST_LABEL = "com.aec.test-runner"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"

_PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.aec.test-runner</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>{runner_path}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{log_path}/runner-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>{log_path}/runner-stderr.log</string>
</dict>
</plist>
"""


def register(runner_path: Path, hour: int, minute: int) -> str:
    """Register the test runner with launchd."""
    try:
        log_path = Path.home() / ".agents-environment-config"
        plist_content = _PLIST_TEMPLATE.format(
            runner_path=runner_path,
            hour=hour,
            minute=minute,
            log_path=log_path,
        )
        PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        PLIST_PATH.write_text(plist_content)
        subprocess.run(
            ["launchctl", "load", str(PLIST_PATH)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return f"Registered with launchd at {hour:02d}:{minute:02d}"
    except Exception as e:
        return f"Failed to register with launchd: {e}"


def unregister() -> str:
    """Unregister the test runner from launchd."""
    try:
        if PLIST_PATH.exists():
            subprocess.run(
                ["launchctl", "unload", str(PLIST_PATH)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            PLIST_PATH.unlink()
        return "Unregistered from launchd"
    except Exception as e:
        return f"Failed to unregister from launchd: {e}"


def is_registered() -> bool:
    """Check if the test runner is registered with launchd."""
    return PLIST_PATH.exists()


def get_next_run() -> Optional[str]:
    """Get the next scheduled run time, or None if not registered."""
    if not PLIST_PATH.exists():
        return None
    try:
        content = PLIST_PATH.read_text()
        # Parse hour and minute from the plist XML
        hour = _extract_integer_after_key(content, "Hour")
        minute = _extract_integer_after_key(content, "Minute")
        if hour is not None and minute is not None:
            return f"{hour:02d}:{minute:02d} daily"
    except Exception:
        pass
    return None


def _extract_integer_after_key(xml_text: str, key: str) -> Optional[int]:
    """Extract the integer value following a <key> element in plist XML."""
    import re

    pattern = rf"<key>{re.escape(key)}</key>\s*<integer>(\d+)</integer>"
    match = re.search(pattern, xml_text)
    if match:
        return int(match.group(1))
    return None
