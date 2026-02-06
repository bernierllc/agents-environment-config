"""Agent tools commands: aec agent-tools {setup|migrate|rollback}"""

from datetime import datetime
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
    AGENT_TOOLS_DIR,
    CLAUDE_DIR,
    CURSOR_DIR,
    VERSION,
    ensure_directory,
    create_symlink,
    remove_symlink,
    is_symlink,
    is_our_symlink,
    get_symlink_target,
)

if HAS_TYPER:
    app = typer.Typer(help="Manage ~/.agent-tools/ directory")
else:
    app = None


def _is_claude_installed() -> bool:
    """Check if Claude Code is installed."""
    import shutil
    return shutil.which("claude") is not None or CLAUDE_DIR.exists()


def _is_cursor_installed() -> bool:
    """Check if Cursor is installed."""
    from ..lib.config import IS_MACOS, IS_WINDOWS

    if CURSOR_DIR.exists() and (CURSOR_DIR / "extensions").exists():
        return True

    if IS_MACOS:
        return Path("/Applications/Cursor.app").exists()

    if IS_WINDOWS:
        # Check common Windows install locations
        local_app_data = Path.home() / "AppData" / "Local" / "Programs" / "cursor"
        return local_app_data.exists()

    return False


def setup() -> None:
    """Create ~/.agent-tools/ structure and symlinks."""
    Console.header("Agent Tools Setup")

    repo_root = get_repo_root()
    if not repo_root:
        Console.error("Could not find agents-environment-config repository")
        raise SystemExit(1)

    Console.print(f"Repository: {Console.path(repo_root)}")
    Console.print(f"Target: {Console.path(AGENT_TOOLS_DIR)}")

    # Create directory structure
    Console.subheader("Creating ~/.agent-tools/ structure...")

    for subdir in ["rules", "agents", "skills", "commands"]:
        ensure_directory(AGENT_TOOLS_DIR / subdir)

    Console.success("Created ~/.agent-tools/ directory structure")

    # Create marker file
    marker = AGENT_TOOLS_DIR / ".aec-managed"
    marker.write_text(
        f"# This directory is managed by agents-environment-config\n"
        f"# Created: {datetime.utcnow().isoformat()}Z\n"
        f"# Source: {repo_root}\n"
        f"# Version: {VERSION}\n"
    )
    Console.success("Created .aec-managed marker file")

    # Create repo symlinks
    Console.subheader("Creating repo symlinks in ~/.agent-tools/...")

    symlinks = [
        (repo_root / ".agent-rules", AGENT_TOOLS_DIR / "rules" / "agents-environment-config", "Rules"),
        (repo_root / ".claude" / "agents", AGENT_TOOLS_DIR / "agents" / "agents-environment-config", "Agents"),
        (repo_root / ".claude" / "skills", AGENT_TOOLS_DIR / "skills" / "agents-environment-config", "Skills"),
        (repo_root / ".cursor" / "commands", AGENT_TOOLS_DIR / "commands" / "agents-environment-config", "Commands"),
    ]

    for source, target, name in symlinks:
        if not source.exists():
            Console.warning(f"{name}: source not found ({source})")
            continue

        if is_symlink(target):
            Console.success(f"{name} (agents-environment-config) (already linked)")
        else:
            if create_symlink(source, target):
                Console.success(f"{name} (agents-environment-config)")
            else:
                Console.error(f"Failed to create {name} symlink")

    # Configure agent-specific symlinks
    Console.subheader("Configuring agent-specific symlinks...")

    if _is_claude_installed():
        Console.print("Claude Code detected - configuring...")
        ensure_directory(CLAUDE_DIR / "agents")
        ensure_directory(CLAUDE_DIR / "skills")

        # Claude symlinks point through ~/.agent-tools/
        claude_links = [
            (AGENT_TOOLS_DIR / "agents" / "agents-environment-config",
             CLAUDE_DIR / "agents" / "agents-environment-config", "Claude agents"),
            (AGENT_TOOLS_DIR / "skills" / "agents-environment-config",
             CLAUDE_DIR / "skills" / "agents-environment-config", "Claude skills"),
        ]

        for source, target, name in claude_links:
            if is_symlink(target):
                Console.success(f"{name} (already linked)")
            else:
                if create_symlink(source, target):
                    Console.success(name)
                else:
                    Console.error(f"Failed to create {name} symlink")
    else:
        Console.info("Claude Code not detected - skipping Claude symlinks")

    if _is_cursor_installed():
        Console.print("Cursor detected - configuring...")
        ensure_directory(CURSOR_DIR / "rules")
        ensure_directory(CURSOR_DIR / "commands")

        # Cursor rules point directly to repo (needs frontmatter)
        cursor_rules_src = repo_root / ".cursor" / "rules"
        cursor_rules_dst = CURSOR_DIR / "rules" / "agents-environment-config"

        if is_symlink(cursor_rules_dst):
            Console.success("Cursor rules (with frontmatter) (already linked)")
        else:
            if create_symlink(cursor_rules_src, cursor_rules_dst):
                Console.success("Cursor rules (with frontmatter)")
            else:
                Console.error("Failed to create Cursor rules symlink")

        # Cursor commands through ~/.agent-tools/
        cursor_cmd_src = AGENT_TOOLS_DIR / "commands" / "agents-environment-config"
        cursor_cmd_dst = CURSOR_DIR / "commands" / "agents-environment-config"

        if is_symlink(cursor_cmd_dst):
            Console.success("Cursor commands (already linked)")
        else:
            if create_symlink(cursor_cmd_src, cursor_cmd_dst):
                Console.success("Cursor commands")
            else:
                Console.error("Failed to create Cursor commands symlink")
    else:
        Console.info("Cursor not detected - skipping Cursor symlinks")

    # Summary
    Console.header("Setup Complete")
    Console.success("~/.agent-tools/ directory structure created")
    Console.print()
    Console.print("Directory Structure:")
    Console.print("  ~/.agent-tools/")
    Console.print("  ├── .aec-managed              # Marker file")
    Console.print("  ├── rules/")
    Console.print("  │   ├── agents-environment-config/ → repo/.agent-rules/")
    Console.print("  │   └── [your rules here]")
    Console.print("  ├── agents/")
    Console.print("  │   └── agents-environment-config/ → repo/.claude/agents/")
    Console.print("  ├── skills/")
    Console.print("  │   └── agents-environment-config/ → repo/.claude/skills/")
    Console.print("  └── commands/")
    Console.print("      └── agents-environment-config/ → repo/.cursor/commands/")


def migrate(dry_run: bool = False) -> None:
    """Migrate from old symlink structure to new."""
    Console.header("Agent Tools Migration")

    if dry_run:
        Console.warning("DRY RUN MODE - No changes will be made\n")

    repo_root = get_repo_root()
    if not repo_root:
        Console.error("Could not find agents-environment-config repository")
        raise SystemExit(1)

    # Check if already migrated
    marker = AGENT_TOOLS_DIR / ".aec-managed"
    if marker.exists():
        Console.info("Migration marker found - structure already exists")

        try:
            response = input("Re-run migration to update symlinks? (y/N): ").strip().lower()
        except EOFError:
            response = "n"

        if response != "y":
            Console.warning("Migration skipped")
            return

    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path.home() / f".agent-tools-backup-{timestamp}"

    Console.subheader("Recording existing symlinks for backup...")

    if not dry_run:
        ensure_directory(backup_dir)

    # Find and backup existing symlinks
    symlinks_to_backup = [
        CLAUDE_DIR / "agents" / "agents-environment-config",
        CLAUDE_DIR / "skills" / "agents-environment-config",
        CURSOR_DIR / "rules" / "agents-environment-config",
        CURSOR_DIR / "commands" / "agents-environment-config",
    ]

    backup_content = []
    for symlink in symlinks_to_backup:
        if is_symlink(symlink):
            target = get_symlink_target(symlink)
            backup_content.append(f"{symlink} -> {target}")
            if dry_run:
                Console.info(f"Would record: {symlink}")
            else:
                Console.success(f"Recorded: {symlink}")

    if not dry_run and backup_content:
        (backup_dir / "symlinks.txt").write_text("\n".join(backup_content))
        Console.success(f"Backup saved to: {backup_dir / 'symlinks.txt'}")

    # Remove old symlinks
    Console.subheader("Removing old symlinks...")
    for symlink in symlinks_to_backup:
        if is_symlink(symlink):
            if dry_run:
                Console.info(f"Would remove: {symlink}")
            else:
                remove_symlink(symlink)
                Console.success(f"Removed: {symlink}")

    # Run setup to create new structure
    if not dry_run:
        setup()

    Console.header("Migration Summary")
    if dry_run:
        Console.warning("DRY RUN COMPLETE - No changes were made")
        Console.print("\nRun without --dry-run to apply changes.")
    else:
        Console.success("Migration completed successfully")
        Console.print(f"\nBackup: {Console.path(backup_dir)}")
        Console.print(f"\nTo rollback: {Console.cmd(f'python -m aec agent-tools rollback {backup_dir}')}")


def rollback(backup_dir: str) -> None:
    """Rollback migration from a backup."""
    Console.header("Agent Tools Rollback")

    backup_path = Path(backup_dir)

    if not backup_path.exists():
        Console.error(f"Backup directory not found: {backup_path}")
        raise SystemExit(1)

    symlinks_file = backup_path / "symlinks.txt"
    if not symlinks_file.exists():
        Console.error("No symlinks.txt found in backup directory")
        raise SystemExit(1)

    Console.print(f"Backup source: {Console.path(backup_path)}")

    # Show what will be restored
    Console.subheader("Backed up symlinks:")
    content = symlinks_file.read_text()
    for line in content.strip().split("\n"):
        Console.print(f"  {line}")

    Console.print()
    Console.warning("This will:")
    Console.print("  1. Remove current ~/.agent-tools/ directory")
    Console.print("  2. Remove current agent symlinks")
    Console.print("  3. Restore the old symlinks from backup")
    Console.print()

    try:
        response = input("Continue with rollback? (y/N): ").strip().lower()
    except EOFError:
        response = "n"

    if response != "y":
        Console.warning("Rollback cancelled")
        return

    # Remove current symlinks
    Console.subheader("Removing current symlinks...")
    symlinks_to_remove = [
        CLAUDE_DIR / "agents" / "agents-environment-config",
        CLAUDE_DIR / "skills" / "agents-environment-config",
        CURSOR_DIR / "rules" / "agents-environment-config",
        CURSOR_DIR / "commands" / "agents-environment-config",
        AGENT_TOOLS_DIR / "rules" / "agents-environment-config",
        AGENT_TOOLS_DIR / "agents" / "agents-environment-config",
        AGENT_TOOLS_DIR / "skills" / "agents-environment-config",
        AGENT_TOOLS_DIR / "commands" / "agents-environment-config",
    ]

    for symlink in symlinks_to_remove:
        if is_symlink(symlink):
            remove_symlink(symlink)
            Console.success(f"Removed: {symlink}")

    # Remove ~/.agent-tools/ if managed by us
    Console.subheader("Removing ~/.agent-tools/...")
    marker = AGENT_TOOLS_DIR / ".aec-managed"
    if marker.exists():
        import shutil
        shutil.rmtree(AGENT_TOOLS_DIR)
        Console.success("Removed ~/.agent-tools/")
    else:
        Console.warning("~/.agent-tools/ doesn't have .aec-managed marker - preserving")

    # Restore old symlinks
    Console.subheader("Restoring old symlinks...")
    for line in content.strip().split("\n"):
        if " -> " not in line:
            continue

        symlink_path, target = line.split(" -> ", 1)
        symlink_path = Path(symlink_path.strip())
        target = Path(target.strip())

        ensure_directory(symlink_path.parent)

        if target.exists():
            if create_symlink(target, symlink_path):
                Console.success(f"Restored: {symlink_path} -> {target}")
            else:
                Console.error(f"Failed to restore: {symlink_path}")
        else:
            Console.warning(f"Target doesn't exist, creating anyway: {symlink_path} -> {target}")
            create_symlink(target, symlink_path)

    Console.header("Rollback Complete")
    Console.success("Restored old symlink structure")
    Console.print(f"\nThe backup has been preserved at: {backup_path}")
    Console.print(f"\nTo re-run migration: {Console.cmd('python -m aec agent-tools migrate')}")


# Typer command decorators (if available)
if HAS_TYPER:
    @app.command("setup")
    def setup_cmd():
        """Create ~/.agent-tools/ structure and symlinks."""
        setup()

    @app.command("migrate")
    def migrate_cmd(
        dry_run: bool = typer.Option(False, "--dry-run", help="Preview without making changes"),
    ):
        """Migrate from old symlink structure to new."""
        migrate(dry_run)

    @app.command("rollback")
    def rollback_cmd(
        backup_dir: str = typer.Argument(..., help="Backup directory to restore from"),
    ):
        """Rollback migration from a backup."""
        rollback(backup_dir)
