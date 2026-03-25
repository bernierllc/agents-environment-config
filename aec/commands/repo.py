"""Repository setup commands: aec repo {setup|list|update}"""

import os
import re
import shutil
import stat
from pathlib import Path
from typing import Optional, List

try:
    import typer
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from ..lib import (
    Console,
    IS_MACOS,
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
    detect_agents,
    generate_raycast_script,
    VERSION,
    get_agent_files,
    get_gitignore_patterns,
    get_migration_files,
    AGENT_TOOLS_DIR,
)
from ..lib.config import load_env_file
from ..lib.git import clone_repo

if HAS_TYPER:
    app = typer.Typer(help="Manage project repositories")
else:
    app = None

# Agent files derived from agents.json registry
AGENT_FILES = get_agent_files()


def _resolve_project_path(path_input: str) -> Path:
    """Resolve a project name or path to an absolute path."""
    p = Path(path_input).expanduser()

    # Check if it's an absolute path (works on both Unix and Windows)
    if p.is_absolute():
        return p.resolve()

    # If it looks like a relative path (contains separators or is . or ..),
    # resolve it relative to cwd instead of treating it as a project name
    if os.sep in path_input or path_input in (".", "..") or path_input.startswith(("./", "../")):
        return Path(path_input).resolve()

    # Otherwise, it's a project name - look in projects directory
    return get_projects_dir() / path_input


def _create_directories(project_dir: Path, dry_run: bool = False) -> None:
    """Create required directories in the project."""
    from ..lib.preferences import get_setting

    Console.subheader("Creating directories...")

    plans_dir = get_setting("plans_dir") or "plans"

    dirs = [
        project_dir / ".cursor" / "rules",
        project_dir / "docs",
        project_dir / plans_dir,
    ]

    for d in dirs:
        if dry_run:
            if not d.exists():
                Console.info(f"Would create: {d}")
            else:
                Console.success(f"{d} (already exists)")
        else:
            ensure_directory(d)

    if not dry_run:
        Console.success(f"Created .cursor/rules/, docs/, {plans_dir}/")


def _copy_agent_files(project_dir: Path, repo_root: Path, dry_run: bool = False) -> None:
    """Copy agent files from repo to project."""
    Console.subheader("Copying agent files...")

    for filename in AGENT_FILES:
        source = repo_root / "templates" / filename
        target = project_dir / filename

        if not source.exists():
            Console.warning(f"{filename} not found in templates/")
            continue

        if target.exists():
            Console.skip(f"{filename} already exists (skipping)")
        elif dry_run:
            Console.info(f"Would copy: {filename}")
        else:
            if copy_file(source, target):
                Console.success(f"Copied {filename}")
            else:
                Console.error(f"Failed to copy {filename}")

    # Copy CURSOR.mdc
    cursor_src = repo_root / "templates" / ".cursor" / "rules" / "CURSOR.mdc"
    cursor_dst = project_dir / ".cursor" / "rules" / "CURSOR.mdc"

    if cursor_src.exists():
        if cursor_dst.exists():
            Console.skip("CURSOR.mdc already exists (skipping)")
        elif dry_run:
            Console.info("Would copy: CURSOR.mdc to .cursor/rules/")
        else:
            if copy_file(cursor_src, cursor_dst):
                Console.success("Copied CURSOR.mdc to .cursor/rules/")
            else:
                Console.error("Failed to copy CURSOR.mdc")


# Mapping of optional feature keys to their rule source files (relative to repo root)
OPTIONAL_RULE_FILES = {
    "leave-it-better": ".cursor/rules/general/leave-it-better.mdc",
}


def _copy_optional_rules(project_dir: Path, repo_root: Path, dry_run: bool = False) -> None:
    """Copy enabled optional rule files to the project."""
    from ..lib.preferences import get_preference

    for feature_key, rule_path in OPTIONAL_RULE_FILES.items():
        preference = get_preference(feature_key)

        # Only copy if explicitly enabled (True), skip if False or None
        if preference is not True:
            continue

        source = repo_root / rule_path
        if not source.exists():
            Console.warning(f"Optional rule source not found: {rule_path}")
            continue

        # Preserve the relative path structure under .cursor/rules/
        relative = Path(rule_path).relative_to(".cursor/rules")
        target = project_dir / ".cursor" / "rules" / relative

        if target.exists():
            Console.skip(f"{relative} already exists (skipping)")
        elif dry_run:
            Console.info(f"Would copy optional rule: {relative}")
        else:
            # Ensure parent directory exists
            ensure_directory(target.parent)

            if copy_file(source, target):
                Console.success(f"Added optional rule to .cursor/rules/{relative}")
            else:
                Console.error(f"Failed to copy optional rule: {relative}")


def _migrate_plans_dir(project_dir: Path, dry_run: bool = False) -> None:
    """Migrate legacy plans directories to the configured plans_dir.

    Checks for legacy locations (plans/, docs/plans/) and moves files
    to the target plans directory if they differ. Skips files that
    already exist in the target. Removes empty legacy dirs after migration.
    """
    from ..lib.preferences import get_setting

    plans_dir = get_setting("plans_dir") or "plans"
    target = project_dir / plans_dir

    legacy_dirs = [
        project_dir / "plans",
        project_dir / "docs" / "plans",
    ]

    for legacy in legacy_dirs:
        # Skip if legacy dir doesn't exist or has no files
        if not legacy.is_dir():
            continue

        # Skip if legacy IS the target (resolved to same path)
        if legacy.resolve() == target.resolve():
            continue

        files = list(legacy.iterdir())
        if not files:
            continue

        if not dry_run:
            # Ensure target directory exists
            ensure_directory(target)

        migrated = 0
        skipped = 0
        for item in files:
            dest = target / item.name
            if dest.exists():
                Console.skip(f"  {item.name} already exists in {plans_dir}/ (skipping)")
                skipped += 1
            elif dry_run:
                Console.info(f"  Would migrate: {item.name} -> {plans_dir}/")
                migrated += 1
            else:
                shutil.move(str(item), str(dest))
                migrated += 1

        if migrated:
            if dry_run:
                Console.info(
                    f"Would migrate {migrated} item(s) from {legacy.relative_to(project_dir)}/ to {plans_dir}/"
                )
            else:
                Console.success(
                    f"Migrated {migrated} item(s) from {legacy.relative_to(project_dir)}/ to {plans_dir}/"
                )
        if skipped:
            Console.info(f"Skipped {skipped} item(s) already in {plans_dir}/")

        # Remove empty legacy directory
        if not dry_run:
            remaining = list(legacy.iterdir())
            if not remaining:
                legacy.rmdir()
                Console.info(f"Removed empty {legacy.relative_to(project_dir)}/")


def _make_safe_name(project_name: str) -> str:
    """Convert a project name to a safe filename component (lowercase, alphanumeric, hyphens)."""
    safe = project_name.lower()
    safe = re.sub(r"[^a-z0-9-]", "-", safe)
    safe = re.sub(r"-+", "-", safe)
    safe = safe.strip("-")
    return safe


def _generate_raycast_scripts(
    project_dir: Path,
    project_name: str,
    repo_root: Path,
    dry_run: bool = False,
) -> None:
    """Detect installed agents and generate Raycast launcher scripts.

    Only runs on macOS since Raycast is a macOS application.
    """
    if not IS_MACOS:
        Console.info("Raycast is macOS only - skipping script generation on this platform.")
        return

    detected = detect_agents()

    if not detected:
        Console.warning("No supported agents detected on this machine.")
        Console.print("  Supported agents: claude, cursor, gemini, qwen, codex")
        Console.print("  Install an agent and re-run setup to generate Raycast scripts.")
        return

    Console.subheader("Detected agents:")
    for agent_name in detected:
        Console.success(agent_name)

    if dry_run:
        # Skip prompt, report what would happen
        raycast_dir = repo_root / "raycast_scripts"
        safe_name = _make_safe_name(project_name)
        script_count = 0

        for agent_name, agent_config in detected.items():
            script_path = raycast_dir / f"{agent_name}-{safe_name}.sh"
            Console.info(f"Would create script: {script_path}")
            script_count += 1

            if agent_config.get("has_resume", False):
                resume_path = raycast_dir / f"{agent_name}-{safe_name}-resume.sh"
                Console.info(f"Would create script: {resume_path}")
                script_count += 1

        Console.info(f"Would create {script_count} Raycast script(s)")
        return

    Console.print()
    try:
        response = input("Generate Raycast scripts for these agents? (Y/n): ").strip().lower()
    except EOFError:
        response = "y"

    if response == "n":
        Console.warning("Skipped Raycast script generation.")
        return

    raycast_dir = repo_root / "raycast_scripts"
    raycast_dir.mkdir(exist_ok=True)

    safe_name = _make_safe_name(project_name)
    abs_project_path = str(project_dir.resolve())
    script_count = 0

    for agent_name, agent_config in detected.items():
        # Generate main script
        content = generate_raycast_script(
            agent_name=agent_name,
            agent_config=agent_config,
            project_name=project_name,
            project_path=abs_project_path,
            is_resume=False,
        )
        script_path = raycast_dir / f"{agent_name}-{safe_name}.sh"
        script_path.write_text(content)
        script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        script_count += 1

        # Generate resume variant if supported
        if agent_config.get("has_resume", False):
            resume_content = generate_raycast_script(
                agent_name=agent_name,
                agent_config=agent_config,
                project_name=project_name,
                project_path=abs_project_path,
                is_resume=True,
            )
            resume_path = raycast_dir / f"{agent_name}-{safe_name}-resume.sh"
            resume_path.write_text(resume_content)
            resume_path.chmod(resume_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            script_count += 1

    Console.success(f"Created {script_count} Raycast script(s) in {raycast_dir}")


def _update_gitignore(project_dir: Path, dry_run: bool = False) -> None:
    """Update .gitignore with agent file patterns."""
    Console.subheader("Updating .gitignore...")

    gitignore_path = project_dir / ".gitignore"

    # Read existing content
    existing_patterns: set[str] = set()
    if gitignore_path.exists():
        existing_patterns = set(gitignore_path.read_text().strip().split("\n"))

    # Add missing patterns (call at runtime, not module-level, so settings are fresh)
    gitignore_patterns = get_gitignore_patterns()
    added = []
    for pattern in gitignore_patterns:
        if pattern not in existing_patterns:
            existing_patterns.add(pattern)
            added.append(pattern)

    if not added:
        Console.info("All patterns already present")
        return

    if dry_run:
        for pattern in added:
            Console.info(f"Would add to .gitignore: {pattern}")
    else:
        with open(gitignore_path, "a") as f:
            for pattern in added:
                f.write(f"{pattern}\n")
                Console.success(f"Added {pattern}")


def _needs_migration(project_dir: Path) -> bool:
    """Check if project needs migration to ~/.agent-tools/ references."""
    for filename in get_migration_files():
        filepath = project_dir / filename
        if filepath.exists():
            content = filepath.read_text()
            # Old format: .cursor/rules/*.mdc
            if ".cursor/rules" in content and ".mdc" in content:
                return True
            # Intermediate format: .agent-rules/ (local, not home dir)
            if ".agent-rules/" in content and "~/.agent-tools/" not in content:
                return True
    return False


def _migrate_agent_files(project_dir: Path, dry_run: bool = False) -> int:
    """Migrate agent files to ~/.agent-tools/ references."""
    import re

    home_rules = "~/.agent-tools/rules/agents-environment-config"

    Console.subheader("Checking for path migrations...")
    changes = 0

    for filename in get_migration_files():
        filepath = project_dir / filename

        if not filepath.exists():
            continue

        content = filepath.read_text()
        needs_update = False

        # Check for old .cursor/rules/*.mdc format
        if ".cursor/rules" in content and ".mdc" in content:
            needs_update = True

        # Check for intermediate .agent-rules/ format (local, not home dir)
        if ".agent-rules/" in content and "~/.agent-tools/" not in content:
            needs_update = True

        if needs_update:
            if dry_run:
                Console.warning(f"Would update: {filename}")
                changes += 1
            else:
                new_content = content

                # Phase 1: .cursor/rules/*.mdc -> home dir paths
                new_content = re.sub(
                    r'\.cursor/rules/([^`]*?)\.mdc',
                    home_rules + r'/\1.md',
                    new_content
                )
                new_content = new_content.replace(
                    "Read relevant `.cursor/rules",
                    f"Read relevant `{home_rules}"
                )
                new_content = new_content.replace(
                    "Rules are organized in `.cursor/rules",
                    f"Rules are organized in `{home_rules}"
                )

                # Phase 2: .agent-rules/ -> home dir paths
                new_content = re.sub(
                    r'(?<!\~/)\.agent-rules/([^`]*?)\.md',
                    home_rules + r'/\1.md',
                    new_content
                )
                new_content = new_content.replace(
                    "Read relevant `.agent-rules",
                    f"Read relevant `{home_rules}"
                )
                new_content = new_content.replace(
                    "Rules are organized in `.agent-rules",
                    f"Rules are organized in `{home_rules}"
                )

                filepath.write_text(new_content)
                Console.success(f"Updated {filename}")
                changes += 1
        else:
            Console.success(f"{filename} already up to date")

    return changes


def _setup_lint_hooks(project_dir: Path, batch: bool = False) -> None:
    """Configure lint hooks for detected AI agents.

    Detects languages in the project, determines which agents support hooks,
    and writes hook configuration files for each qualifying agent.

    Args:
        project_dir: Path to the project root directory.
        batch: If True, skip interactive prompts and use all detected languages.
    """
    from ..lib.preferences import get_setting, set_setting
    from ..lib.hooks import (
        LANGUAGE_HOOKS,
        AGENT_HOOK_CONFIGS,
        detect_languages,
        write_hook_config,
    )

    Console.subheader("Setting up lint hooks...")

    # Step 1: Get or prompt for hook_mode
    hook_mode = get_setting("hook_mode")
    if hook_mode is None:
        if batch:
            hook_mode = "auto"
        else:
            Console.print("\nLint hook mode determines when hooks are installed:")
            Console.print("  1) auto     - Install hooks for all detected languages")
            Console.print("  2) per-repo - Ask which languages per project")
            Console.print("  3) never    - Never install lint hooks")
            Console.print()
            try:
                choice = input("Choose hook mode [1]: ").strip() or "1"
            except EOFError:
                choice = "1"

            mode_map = {"1": "auto", "2": "per-repo", "3": "never"}
            hook_mode = mode_map.get(choice, "auto")

        set_setting("hook_mode", hook_mode)
        Console.info(f"Saved hook_mode={hook_mode}")

    # Step 2: If never, bail out
    if hook_mode == "never":
        Console.skip("Lint hooks disabled (hook_mode=never)")
        return

    # Step 3: Detect languages
    languages = detect_languages(project_dir)
    if not languages:
        Console.info("No supported languages detected, skipping lint hooks")
        return

    # Step 4: Determine which languages to use
    if hook_mode == "auto" or batch:
        selected_languages = languages
    else:
        # per-repo mode: prompt user
        Console.print("\nDetected languages:")
        for i, lang in enumerate(languages, 1):
            display = LANGUAGE_HOOKS[lang]["display_name"]
            Console.print(f"  {i}) {display}")
        all_option = len(languages) + 1
        none_option = len(languages) + 2
        Console.print(f"  {all_option}) All detected")
        Console.print(f"  {none_option}) None")
        Console.print()

        try:
            choice = input("Select languages for lint hooks: ").strip()
        except EOFError:
            choice = str(all_option)

        if choice == str(none_option):
            Console.skip("No languages selected, skipping lint hooks")
            return
        elif choice == str(all_option):
            selected_languages = languages
        else:
            # Single language selection
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(languages):
                    selected_languages = [languages[idx]]
                else:
                    selected_languages = languages
            except (ValueError, IndexError):
                selected_languages = languages

    # Step 5: Gather commands for selected languages
    commands = [LANGUAGE_HOOKS[lang]["command"] for lang in selected_languages]

    # Step 6: Detect agents and filter to those with hook support
    detected = detect_agents()
    qualifying_agents = {
        name: config
        for name, config in detected.items()
        if config.get("supports_hooks") and name in AGENT_HOOK_CONFIGS
    }

    if not qualifying_agents:
        Console.info("No agents with hook support detected")
        return

    # Step 7: Write hook configs for each qualifying agent
    for agent_key in qualifying_agents:
        agent_config_path = project_dir / AGENT_HOOK_CONFIGS[agent_key]["config_path"]

        if agent_config_path.exists() and hook_mode == "per-repo" and not batch:
            Console.print(f"\n{agent_key}: {agent_config_path.name} already exists")
            Console.print("  1) Skip")
            Console.print("  2) Merge hooks into existing config")
            Console.print("  3) Show config (don't write)")
            Console.print()
            try:
                action = input("Choice [1]: ").strip() or "1"
            except EOFError:
                action = "1"

            action_map = {"1": "skip", "2": "merge", "3": "show"}
            mode = action_map.get(action, "skip")
        else:
            mode = "auto"

        result = write_hook_config(project_dir, agent_key, commands, mode=mode)

        if result == "created":
            Console.success(f"Created {AGENT_HOOK_CONFIGS[agent_key]['config_path']}")
        elif result == "merged":
            Console.success(f"Merged hooks into {AGENT_HOOK_CONFIGS[agent_key]['config_path']}")
        elif result == "skipped":
            Console.skip(f"Skipped {agent_key} (config already exists)")
        elif result == "exists":
            Console.skip(f"Skipped {agent_key} (config already exists)")
        elif result == "show":
            from ..lib.hooks import generate_hook_config
            import json
            config = generate_hook_config(agent_key, commands)
            Console.print(f"\n{agent_key} hook config:")
            Console.print(json.dumps(config, indent=2))


def setup(
    path: Optional[str] = None,
    skip_raycast: bool = False,
    batch: bool = False,
    dry_run: bool = False,
) -> None:
    """Setup a project with agent files.

    Args:
        path: Project name or path. If None, prompts interactively.
        skip_raycast: Skip Raycast script creation.
        batch: Batch mode (skip interactive prompts for already-setup projects).
        dry_run: If True, report what would happen without making changes.
    """
    Console.header("Repository Setup")

    # Load .env from repo root (matches bash script behavior)
    load_env_file()

    if path is None:
        try:
            path = input("Enter project name or path: ").strip()
        except EOFError:
            Console.error("No project specified")
            raise SystemExit(1)
        if not path:
            Console.error("No project specified")
            raise SystemExit(1)

    if dry_run:
        Console.warning("DRY RUN MODE - No changes will be made\n")

    repo_root = get_repo_root()
    if not repo_root:
        Console.error("Could not find agents-environment-config repository")
        raise SystemExit(1)

    Console.print(f"Template source: {Console.path(repo_root)}")

    # Check that aec install has been run (rules must exist in home dir)
    rules_install_dir = AGENT_TOOLS_DIR / "rules" / "agents-environment-config"
    if not rules_install_dir.exists():
        Console.error(
            "Agent rules not installed. "
            "Agent files reference rules in ~/.agent-tools/rules/agents-environment-config/ "
            "which does not exist."
        )
        Console.print(f"\nRun this first: {Console.cmd('python -m aec install')}")
        raise SystemExit(1)

    # Resolve path
    project_dir = _resolve_project_path(path)
    project_name = project_dir.name

    Console.print(f"\nProject: {Console.path(project_name)}")
    Console.print(f"Directory: {Console.path(project_dir)}")

    # Check if already set up
    if is_logged(project_dir):
        old_version = get_version(project_dir) or "unknown"

        if dry_run:
            Console.info(f"Previously set up (version {old_version})")
            Console.info("Would check for updates")
            update(str(project_dir), dry_run=True, update_all=False)
            return

        if batch:
            # In batch mode, silently run update instead of showing interactive menu
            Console.info(f"  {project_dir.name}: updating (was {old_version})")
            update(str(project_dir), dry_run=False, update_all=False)
            return

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
        if dry_run:
            Console.info(f"Directory does not exist: {project_dir}")
            Console.info("Would attempt to clone or create directory")
            return

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
    _create_directories(project_dir, dry_run)

    # Migrate legacy plans directories
    _migrate_plans_dir(project_dir, dry_run)

    # Copy agent files
    _copy_agent_files(project_dir, repo_root, dry_run)

    # Copy optional rules based on user preferences
    _copy_optional_rules(project_dir, repo_root, dry_run)

    # Setup lint hooks
    if not dry_run:
        _setup_lint_hooks(project_dir, batch=batch)

    # Update .gitignore
    _update_gitignore(project_dir, dry_run)

    # Log setup
    log_setup(project_dir, dry_run)
    if not dry_run:
        Console.success(f"Logged setup to tracking file")

    # Raycast scripts (macOS only)
    if not skip_raycast:
        if dry_run:
            repo_root_path = get_repo_root()
            if repo_root_path:
                _generate_raycast_scripts(project_dir, project_name, repo_root_path, dry_run=True)
        else:
            Console.print()
            try:
                raycast_response = input("Create Raycast launcher scripts? (y/N): ").strip().lower()
            except EOFError:
                raycast_response = "n"

            if raycast_response == "y":
                repo_root_path = get_repo_root()
                if repo_root_path:
                    _generate_raycast_scripts(project_dir, project_name, repo_root_path)
                else:
                    Console.error("Could not find repo root for Raycast script output directory.")

    # Summary
    if not dry_run:
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
        _update_single_repo(_resolve_project_path(path), dry_run)


def _clean_agentinfo_redundancy(project_dir: Path, dry_run: bool = False) -> None:
    """Check for redundant rule references in AGENTINFO.md.

    AGENTINFO.md should contain project-specific info only. Rule locations
    belong in agent-specific files (CLAUDE.md, GEMINI.md, etc.).
    """
    filepath = project_dir / "AGENTINFO.md"
    if not filepath.exists():
        return

    content = filepath.read_text()
    if any(pattern in content for pattern in [".cursor/rules", ".agent-rules"]):
        if dry_run:
            Console.warning("Would clean: AGENTINFO.md (has redundant rule references)")
            Console.info("  Rule locations belong in agent-specific files (CLAUDE.md, etc.)")
        else:
            Console.warning("AGENTINFO.md may have redundant rule references")
            Console.info("  Manual review recommended:")
            Console.info("  Remove lines referencing .cursor/rules/ or .agent-rules/")
            Console.info("  These are defined in agent-specific files (CLAUDE.md, etc.)")


def _repair_hook_keys(project_dir: Path, dry_run: bool = False) -> None:
    """Fix camelCase hook keys in agent config files.

    Earlier versions of aec wrote 'postToolUse' instead of 'PostToolUse'
    in .claude/settings.json, which Claude Code rejects as invalid.
    """
    from ..lib.hooks import repair_hook_keys

    if dry_run:
        # Still check so we can report what would happen
        results = repair_hook_keys(project_dir)
        for agent_key, status in results.items():
            if status == "fixed":
                Console.warning(f"Would fix hook key casing in {agent_key} config")
        return

    results = repair_hook_keys(project_dir)
    for agent_key, status in results.items():
        if status == "fixed":
            from ..lib.hooks import AGENT_HOOK_CONFIGS
            config_path = AGENT_HOOK_CONFIGS[agent_key]["config_path"]
            Console.success(f"Fixed hook key casing in {config_path}")
        elif status.startswith("error:"):
            Console.warning(f"Could not check {agent_key} hooks: {status[6:]}")


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

    # Fix hook key casing (postToolUse -> PostToolUse)
    _repair_hook_keys(project_dir, dry_run)

    # Check for redundant rule references in AGENTINFO.md
    _clean_agentinfo_redundancy(project_dir, dry_run)

    # Migrate legacy plans directories
    if not dry_run:
        _migrate_plans_dir(project_dir)

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


def setup_all(dry_run: bool = False) -> None:
    """Setup all projects in the configured projects directory."""
    from ..lib.preferences import get_setting
    from .install import _batch_project_setup

    projects_dir = get_setting("projects_dir")
    if not projects_dir:
        Console.error("No projects directory configured. Run 'aec install' first.")
        raise SystemExit(1)

    _batch_project_setup(dry_run)


# Typer command decorators (if available)
if HAS_TYPER:
    @app.command("setup")
    def setup_cmd(
        path: Optional[str] = typer.Argument(None, help="Project name or path"),
        skip_raycast: bool = typer.Option(False, "--skip-raycast", help="Skip Raycast script creation"),
    ):
        """Setup a project with agent files."""
        setup(path, skip_raycast)

    @app.command("list")
    def list_cmd():
        """List all tracked repositories."""
        list_repos()

    @app.command("setup-all")
    def setup_all_cmd():
        """Setup all projects in the configured projects directory."""
        setup_all()

    @app.command("update")
    def update_cmd(
        path: Optional[str] = typer.Argument(None, help="Specific project to update"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Preview without making changes"),
        update_all: bool = typer.Option(False, "--all", help="Update all tracked repos"),
    ):
        """Update tracked repositories with latest configurations."""
        update(path, dry_run, update_all)
