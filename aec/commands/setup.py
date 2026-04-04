"""aec setup -- first-time bootstrap or repo tracking."""

from pathlib import Path

from ..lib import Console
from ..lib.config import AEC_HOME
from ..lib.tracking import log_setup, init_aec_home, is_logged
from ..lib.scope import find_tracked_repo


def run_setup(skip_raycast: bool = False, dry_run: bool = False) -> None:
    """Run first-time install or offer to track the current repo.

    - If AEC is not installed (no AEC_HOME), delegate to full install.
    - If installed and cwd is an untracked git repo, offer to track it.
    - Otherwise, report status.
    """
    if not AEC_HOME.exists():
        from .install import install
        install(dry_run=dry_run)
        return

    repo = find_tracked_repo()
    if repo is None:
        cwd = Path.cwd()
        if (cwd / ".git").exists() and not is_logged(cwd):
            Console.print(f"AEC is already installed. Track {cwd} as a repo?")
            try:
                resp = input("[Y/n]: ").strip().lower()
            except EOFError:
                resp = "n"
            if resp != "n":
                run_setup_path(str(cwd), skip_raycast=skip_raycast, dry_run=dry_run)
                return

    Console.print("AEC is installed and up to date.")
    Console.print(f"  Home: {AEC_HOME}")
    Console.print("  Run `aec doctor` for a health check.")


def run_setup_path(path: str, skip_raycast: bool = False, dry_run: bool = False) -> None:
    """Track a specific repo path.

    Args:
        path: Filesystem path to the project directory.
        skip_raycast: If True, skip Raycast script generation.
        dry_run: If True, report what would happen without making changes.
    """
    project = Path(path).resolve()
    if not project.exists():
        Console.error(f"Path does not exist: {project}")
        raise SystemExit(1)

    if is_logged(project):
        Console.info(f"Already tracked: {project}")
        return

    init_aec_home(dry_run=dry_run)

    if dry_run:
        Console.info(f"Would track: {project}")
        return

    from .repo import setup as repo_setup
    repo_setup(str(project), skip_raycast=skip_raycast, dry_run=dry_run)


def run_setup_all(skip_raycast: bool = False, dry_run: bool = False) -> None:
    """Track all repos in the configured projects directory."""
    from .repo import setup_all
    setup_all(dry_run=dry_run)
