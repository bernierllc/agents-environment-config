"""Discover command: aec discover - Find repos from existing Raycast scripts."""

from pathlib import Path
from typing import Optional

try:
    import typer
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from ..lib import (
    Console,
    get_repo_root,
    discover_from_scripts,
    is_logged,
    log_setup,
    list_repos as tracking_list_repos,
)


def discover(
    dry_run: bool = False,
    auto: bool = False,
) -> None:
    """
    Discover repos from existing Raycast launcher scripts.

    Scans raycast_scripts/ for generated launcher scripts, extracts
    project paths, compares with the tracking log, and optionally
    adds missing paths.

    Args:
        dry_run: Show what would be added without adding it.
        auto: Add missing paths without prompting for confirmation.
    """
    Console.header("Repo Discovery")

    repo_root = get_repo_root()
    if not repo_root:
        Console.error("Could not find agents-environment-config repository")
        raise SystemExit(1)

    raycast_dir = repo_root / "raycast_scripts"
    if not raycast_dir.is_dir():
        Console.error(f"Raycast scripts directory not found: {raycast_dir}")
        Console.info("No scripts to scan.")
        return

    Console.print(f"Scanning {Console.path(raycast_dir)} for project paths...")
    Console.newline()

    # Discover paths from scripts
    discovered_paths = discover_from_scripts(raycast_dir)

    if not discovered_paths:
        Console.info("No project paths found in Raycast scripts.")
        return

    # Count total .sh files for context
    total_scripts = len(list(raycast_dir.glob("*.sh")))

    # Categorize discovered paths
    already_tracked = []
    new_paths = []
    missing_paths = []  # paths that don't exist on disk

    for path in discovered_paths:
        if is_logged(path):
            already_tracked.append(path)
        elif not path.exists():
            missing_paths.append(path)
        else:
            new_paths.append(path)

    # Display results
    Console.print(
        f"Found {Console.bold(str(len(discovered_paths)))} unique paths "
        f"from {Console.bold(str(total_scripts))} Raycast scripts:"
    )
    Console.newline()

    for path in discovered_paths:
        if is_logged(path):
            status = Console.dim("(already tracked)")
        elif not path.exists():
            status = Console._colorize(Console.RED, "(path not found)")
        else:
            status = Console._colorize(Console.YELLOW, "(not tracked)")

        Console.print(f"  {path} {status}")

    Console.newline()

    Console.print(f"Already tracked: {Console._colorize(Console.GREEN, str(len(already_tracked)))}")
    Console.print(f"New paths to add: {Console._colorize(Console.YELLOW, str(len(new_paths)))}")
    if missing_paths:
        Console.print(f"Missing on disk: {Console._colorize(Console.RED, str(len(missing_paths)))}")

    if not new_paths:
        Console.newline()
        Console.success("All discovered paths are already tracked. Nothing to do.")
        return

    Console.newline()

    # Dry run mode - just show what would happen
    if dry_run:
        Console.warning("DRY RUN - No changes will be made")
        Console.newline()
        Console.print("Would add the following paths to tracking:")
        for path in new_paths:
            Console.print(f"  {Console.path(path)}")
        return

    # Auto mode - add without prompting
    if auto:
        _add_paths(new_paths)
        return

    # Interactive mode - prompt for confirmation
    Console.print(f"Add {len(new_paths)} new path(s) to tracking? (y/N): ", end="")
    try:
        response = input().strip().lower()
    except EOFError:
        response = "n"

    if response == "y":
        _add_paths(new_paths)
    else:
        Console.warning("Cancelled")


def _add_paths(paths: list[Path]) -> None:
    """Add discovered paths to the tracking log."""
    for path in paths:
        log_setup(path)
    Console.success(f"Added {len(paths)} path(s) to tracking log")


# Typer command (if available)
if HAS_TYPER:
    def discover_cmd(
        dry_run: bool = typer.Option(
            False, "--dry-run",
            help="Show what would be added without adding it",
        ),
        auto: bool = typer.Option(
            False, "--auto",
            help="Add missing paths without prompting",
        ),
    ):
        """Discover repos from existing Raycast launcher scripts."""
        discover(dry_run=dry_run, auto=auto)
