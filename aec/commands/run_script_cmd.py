"""`aec run-script <item> <script>` -- scope-aware script runner.

Lives in its own module to avoid the circular import that would arise from
registering the command inside `hooks_cmd.py` (which `aec/cli.py` imports).
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import typer

from ..lib.console import Console
from ..lib.scope import find_tracked_repo

_TYPE_TO_PLURAL = {"skill": "skills", "rule": "rules", "agent": "agents"}


def _resolve_item_dir(item_type: str, item_key: str) -> Optional[Path]:
    """Find the installed directory for ``item_type:item_key``.

    Project scope (current tracked repo) wins over global. Returns None if the
    item is not installed in either scope.
    """
    plural = _TYPE_TO_PLURAL.get(item_type)
    if plural is None:
        return None

    candidates: List[Path] = []
    repo = find_tracked_repo()
    if repo is not None:
        candidates.append(repo / ".claude" / plural / item_key)
        if item_type == "rule":
            candidates.append(repo / ".agent-rules" / item_key)
    candidates.append(Path.home() / ".claude" / plural / item_key)
    if item_type == "rule":
        candidates.append(Path.home() / ".agent-tools" / "rules" / item_key)

    for c in candidates:
        if c.exists():
            return c
    return None


def run_script(
    item: str = typer.Argument(
        ..., help="Item in form <type>:<key>, e.g. skill:my-skill"
    ),
    script: str = typer.Argument(
        ..., help="Script filename relative to the item's scripts/ dir"
    ),
    extra: Optional[List[str]] = typer.Argument(None),
) -> None:
    """Resolve <script> from the item's install directory and exec it."""
    if ":" not in item:
        Console.error(
            f"item must be <type>:<key> (got {item!r}); "
            f"valid types: {', '.join(_TYPE_TO_PLURAL)}"
        )
        raise typer.Exit(2)
    item_type, _, item_key = item.partition(":")
    if item_type not in _TYPE_TO_PLURAL:
        Console.error(
            f"unknown item type {item_type!r}; "
            f"valid: {', '.join(_TYPE_TO_PLURAL)}"
        )
        raise typer.Exit(2)

    item_dir = _resolve_item_dir(item_type, item_key)
    if item_dir is None:
        Console.error(f"{item_type}:{item_key} is not installed in this scope")
        raise typer.Exit(2)

    script_path = item_dir / "scripts" / script
    if not script_path.exists():
        Console.error(f"script not found: {script_path}")
        raise typer.Exit(2)

    if not os.access(script_path, os.X_OK):
        try:
            script_path.chmod(script_path.stat().st_mode | 0o111)
        except OSError:
            pass

    cmd = [str(script_path), *(extra or [])]
    proc = subprocess.run(cmd)
    sys.exit(proc.returncode)
