"""Repository setup commands: aec repo {setup|list|update}"""

import shutil
from pathlib import Path
from typing import Optional, List

try:
    import typer
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from ..lib import (
    Console,
    get_repo_root,
    get_projects_dir,
    get_github_orgs,
    ensure_directory,
    copy_file,
    init_aec_home,
    log_setup,
    is_logged,
    get_version,
    list_repos as tracking_list_repos,
    VERSION,
)
from ..lib.git import clone_repo

if HAS_TYPER:
    app = typer.Typer(help="Manage project repositories")
else:
    app = None

# Agent files to copy
AGENT_FILES = ["AGENTINFO.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md", "QWEN.md"]

# Patterns to add to .gitignore
GITIGNORE_PATTERNS = [
    "AGENTINFO.md",
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    "QWEN.md",
    ".cursor/rules",
    "/plans/",
]


def _resolve_project_path(path_input: str) -> Path:
    """Resolve a project name or path to an absolute path."""
    # Check if it's an absolute or home-relative path
    if path_input.startswith("/") or path_input.startswith("~"):
        return Path(path_input).expanduser().resolve()

    # Otherwise, it's a project name - look in projects directory
    return get_projects_dir() / path_input


def _create_directories(project_dir: Path) -> None:
    """Create required directories in the project."""
    Console.subheader("Creating directories...")

    dirs = [
        project_dir / ".cursor" / "rules",
        project_dir / "docs",
        project_dir / "plans",
    ]

    for d in dirs:
        ensure_directory(d)

    Console.success("Created .cursor/rules/, docs/, plans/")


def _copy_agent_files(project_dir: Path, repo_root: Path) -> None:
    """Copy agent files from repo to project."""
    Console.subheader("Copying agent files...")

    for filename in AGENT_FILES:
        source = repo_root / filename
        target = project_dir / filename

        if not source.exists():
            Console.warning(f"{filename} not found in repo")
            continue

        if target.exists():
            Console.skip(f"{filename} already exists (skipping)")
        else:
            if copy_file(source, target):
                Console.success(f"Copied {filename}")
            else:
                Console.error(f"Failed to copy {filename}")

    # Copy CURSOR.mdc
    cursor_src = repo_root / ".cursor" / "rules" / "CURSOR.mdc"
    cursor_dst = project_dir / ".cursor" / "rules" / "CURSOR.mdc"

    if cursor_src.exists():
        if cursor_dst.exists():
            Console.skip("CURSOR.mdc already exists (skipping)")
        else:
            if copy_file(cursor_src, cursor_dst):
                Console.success("Copied CURSOR.mdc to .cursor/rules/")
            else:
                Console.error("Failed to copy CURSOR.mdc")


def _update_gitignore(project_dir: Path) -> None:
    """Update .gitignore with agent file patterns."""
    Console.subheader("Updating .gitignore...")

    gitignore_path = project_dir / ".gitignore"

    # Read existing content
    existing_patterns: set[str] = set()
    if gitignore_path.exists():
        existing_patterns = set(gitignore_path.read_text().strip().split("\n"))

    # Add missing patterns
    added = []
    for pattern in GITIGNORE_PATTERNS:
        if pattern not in existing_patterns:
            existing_patterns.add(pattern)
            added.append(pattern)

    # Write back
    if added:
        with open(gitignore_path, "a") as f:
            for pattern in added:
                f.write(f"{pattern}\n")
                Console.success(f"Added {pattern}")
    else:
        Console.info("All patterns already present")


def _needs_migration(project_dir: Path) -> bool:
    """Check if project needs migration to .agent-rules/ references."""
    for filename in ["CLAUDE.md", "AGENTS.md", "GEMINI.md", "QWEN.md"]:
        filepath = project_dir / filename
        if filepath.exists():
            content = filepath.read_text()
            if ".cursor/rules" in content and ".mdc" in content:
                return True
    return False


def _migrate_agent_files(project_dir: Path, dry_run: bool = False) -> int:
    """Migrate agent files from .cursor/rules/ to .agent-rules/ references."""
    import re

    Console.subheader(f"Checking for .agent-rules migration...")
    changes = 0

    for filename in ["CLAUDE.md", "AGENTS.md", "GEMINI.md", "QWEN.md"]:
        filepath = project_dir / filename

        if not filepath.exists():
            continue

        content = filepath.read_text()

        if ".cursor/rules" in content and ".mdc" in content:
            if dry_run:
                Console.warning(f"Would update: {filename}")
                changes += 1
            else:
                # Replace .cursor/rules/*.mdc with .agent-rules/*.md
                new_content = re.sub(
                    r'\.cursor/rules/([^`]*?)\.mdc',
                    r'.agent-rules/\1.md',
                    content
                )
                # Also update text references
                new_content = new_content.replace(
                    "Read relevant `.cursor/rules",
                    "Read relevant `.agent-rules"
                )
                new_content = new_content.replace(
                    "Rules are organized in `.cursor/rules",
                    "Rules are organized in `.agent-rules"
                )

                filepath.write_text(new_content)
                Console.success(f"Updated {filename}")
                changes += 1
        else:
            Console.success(f"{filename} already uses .agent-rules/")

    return changes


def setup(
    path: str,
    skip_raycast: bool = False,
) -> None:
    """Setup a project with agent files."""
    Console.header("Repository Setup")

    repo_root = get_repo_root()
    if not repo_root:
        Console.error("Could not find agents-environment-config repository")
        raise SystemExit(1)

    Console.print(f"Template source: {Console.path(repo_root)}")

    # Resolve path
    project_dir = _resolve_project_path(path)
    project_name = project_dir.name

    Console.print(f"\nProject: {Console.path(project_name)}")
    Console.print(f"Directory: {Console.path(project_dir)}")

    # Check if already set up
    if is_logged(project_dir):
        old_version = get_version(project_dir) or "unknown"
        Console.info(f"Previously set up (version {old_version})")
        Console.print("\nOptions:")
        Console.print("  1) Check for updates (recommended)")
        Console.print("  2) Fresh setup (skip existing files)")
        Console.print("  3) Cancel")
        Console.print()

        try:
            choice = input("Choice [1]: ").strip() or "1"
        except EOFError:
            choice = "1"

        if choice == "1":
            update(str(project_dir), dry_run=False, update_all=False)
            return
        elif choice == "3":
            Console.warning("Cancelled")
            return

    # Check if directory exists
    if not project_dir.exists():
        Console.warning("Directory does not exist.")

        # Try to clone from GitHub
        cloned = False
        for org in get_github_orgs():
            Console.info(f"Trying to clone from {org}/{project_name}...")
            success, message = clone_repo(org, project_name, project_dir)
            if success:
                Console.success(message)
                cloned = True
                break

        if not cloned:
            try:
                response = input("Create new directory? (y/N): ").strip().lower()
            except EOFError:
                response = "n"

            if response == "y":
                project_dir.mkdir(parents=True)
                Console.success("Created directory")
            else:
                Console.error("Aborted")
                return

    # Create directories
    _create_directories(project_dir)

    # Copy agent files
    _copy_agent_files(project_dir, repo_root)

    # Update .gitignore
    _update_gitignore(project_dir)

    # Log setup
    log_setup(project_dir)
    Console.success(f"Logged setup to tracking file")

    # Summary
    Console.header("Setup Complete")
    Console.print(f"Project ready at: {Console.path(project_dir)}")
    Console.print("\nNext steps:")
    Console.print(f"  1. {Console.bold('Edit AGENTINFO.md')} with your project-specific info")
    Console.print("  2. Review .cursor/rules/CURSOR.mdc for Cursor settings")
    Console.print("  3. Start coding with your AI assistant!")
    Console.print()
    Console.print(f"Future updates: {Console.cmd('python -m aec repo update --all')}")


def list_repos() -> None:
    """List all tracked repositories."""
    Console.header("Tracked Repositories")

    repos = tracking_list_repos()

    if not repos:
        Console.print("No repositories have been set up yet.")
        Console.print(f"\nRun: {Console.cmd('python -m aec repo setup <path>')}")
        return

    Console.print(f"{'Timestamp':<26} | {'Version':<7} | Path")
    Console.print("-" * 26 + "-+-" + "-" * 7 + "-+-" + "-" * 30)

    for repo in repos:
        status = Console._colorize(Console.GREEN, "✓") if repo.exists else Console._colorize(Console.RED, "✗")
        Console.print(f"{repo.timestamp} | {repo.version:<7} | {repo.path} {status}")

    Console.print()
    Console.print(f"Legend: {Console._colorize(Console.GREEN, '✓')} = exists, {Console._colorize(Console.RED, '✗')} = not found")


def update(
    path: Optional[str] = None,
    dry_run: bool = False,
    update_all: bool = False,
) -> None:
    """Update tracked repositories."""
    if update_all or path is None:
        _update_all_repos(dry_run)
    else:
        _update_single_repo(Path(path), dry_run)


def _update_single_repo(project_dir: Path, dry_run: bool = False) -> None:
    """Update a single repository."""
    if not project_dir.exists():
        Console.error(f"Directory not found: {project_dir}")
        return

    old_version = get_version(project_dir) or "unknown"
    Console.print(f"\nUpdating: {Console.path(project_dir)}")
    Console.print(f"  Logged version: {old_version} -> Current: {VERSION}")

    # Check for migrations
    if _needs_migration(project_dir):
        _migrate_agent_files(project_dir, dry_run)

    # Update log
    if not dry_run:
        log_setup(project_dir)

    Console.success("Update complete")


def _update_all_repos(dry_run: bool = False) -> None:
    """Update all tracked repositories."""
    Console.header("Update All Tracked Repositories")

    repos = tracking_list_repos()

    if not repos:
        Console.print("No repositories have been set up yet.")
        return

    if dry_run:
        Console.warning("DRY RUN MODE - No changes will be made\n")

    total = len(repos)
    updated = 0
    skipped = 0

    for repo in repos:
        if repo.exists:
            _update_single_repo(repo.path, dry_run)
            updated += 1
        else:
            Console.warning(f"Skipping (not found): {repo.path}")
            skipped += 1

    Console.header("Update Summary")
    Console.print(f"Total tracked: {total}")
    Console.print(f"Updated: {Console._colorize(Console.GREEN, str(updated))}")
    Console.print(f"Skipped: {Console._colorize(Console.YELLOW, str(skipped))}")

    if dry_run:
        Console.print("\nRun without --dry-run to apply changes.")


# Typer command decorators (if available)
if HAS_TYPER:
    @app.command("setup")
    def setup_cmd(
        path: str = typer.Argument(..., help="Project name or path"),
        skip_raycast: bool = typer.Option(False, "--skip-raycast", help="Skip Raycast script creation"),
    ):
        """Setup a project with agent files."""
        setup(path, skip_raycast)

    @app.command("list")
    def list_cmd():
        """List all tracked repositories."""
        list_repos()

    @app.command("update")
    def update_cmd(
        path: Optional[str] = typer.Argument(None, help="Specific project to update"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Preview without making changes"),
        update_all: bool = typer.Option(False, "--all", help="Update all tracked repos"),
    ):
        """Update tracked repositories with latest configurations."""
        update(path, dry_run, update_all)
