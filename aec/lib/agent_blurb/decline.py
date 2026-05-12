"""Decline state for the agent-blurb feature.

Stored in a sibling file rather than inside agent-blurb.json so that the
"one concern per file" rule holds (relevant for parallel agent safety).
See spec §5.1 and §13.1.
"""

import json
from pathlib import Path
from typing import Optional

from aec.lib.atomic_write import atomic_write_text

DECLINE_FILENAME = "agent-blurb-decline.json"


def _decline_path(scope: str, root: Optional[Path] = None) -> Path:
    if scope == "project":
        if root is None:
            raise ValueError("project scope requires root")
        return root / ".aec" / DECLINE_FILENAME
    if scope == "global":
        return Path.home() / ".aec" / DECLINE_FILENAME
    raise ValueError(f"Unknown scope: {scope!r}")


def is_declined(scope: str, root: Optional[Path] = None) -> bool:
    return _decline_path(scope, root).exists()


def record_decline(scope: str, aec_version: str, root: Optional[Path] = None) -> None:
    path = _decline_path(scope, root)
    atomic_write_text(
        path,
        json.dumps({"declined": True, "declined_at_version": aec_version}, indent=2) + "\n",
    )


def clear_decline(scope: str, root: Optional[Path] = None) -> None:
    path = _decline_path(scope, root)
    if path.exists():
        path.unlink()


def _major(version: str) -> int:
    return int(version.split(".")[0])


def should_reprompt(scope: str, current_version: str, root: Optional[Path] = None) -> bool:
    """Re-prompt only on major version bumps (per spec §13.1 default)."""
    path = _decline_path(scope, root)
    if not path.exists():
        return True
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True
    declined_version = data.get("declined_at_version", "0.0.0")
    return _major(current_version) > _major(declined_version)
