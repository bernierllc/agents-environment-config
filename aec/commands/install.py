"""Install command: aec install - Full setup of agents-environment-config."""

import json
from pathlib import Path
from typing import Optional

try:
    import typer
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from ..lib import Console, get_repo_root, init_aec_home
from ..lib.git import is_git_repo, has_gitmodules, init_submodules, update_submodule
from . import agent_tools, rules


def _update_submodules_from_config(repo_root: Path, dry_run: bool = False) -> None:
    """Update submodules listed in scripts/sync-config.json.

    Args:
        repo_root: Path to the repository root.
        dry_run: If True, report what would happen without making changes.
    """
    sync_config_path = repo_root / "scripts" / "sync-config.json"
    if not sync_config_path.exists():
        Console.warning("scripts/sync-config.json not found — skipping submodule updates")
        return
    try:
        sync_config = json.loads(sync_config_path.read_text())
    except json.JSONDecodeError:
        Console.warning("scripts/sync-config.json is malformed — skipping submodule updates")
        return
    for key, entry in sync_config.get("submodules", {}).items():
        sub_path = entry.get("path")
        if not sub_path:
            Console.warning(f"Submodule '{key}' has no 'path' — skipping")
            continue
        display = entry.get("display_name", key)
        if (repo_root / sub_path).exists():
            Console.print(f"  Updating {display}...")
            success, result = update_submodule(repo_root, sub_path, dry_run)
            if success:
                Console.success(f"{display.capitalize()} updated to {result}")
            else:
                Console.warning(f"{display}: {result}")


def _cleanup_legacy_symlinks(
    claude_skills_dir: Optional[Path] = None,
    agent_tools_skills_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> None:
    """Remove AEC-created skill symlinks from known paths.

    Only removes symlinks whose targets contain 'agent-tools' or
    'agents-environment-config' in the resolution chain.
    """
    if claude_skills_dir is None:
        from ..lib import CLAUDE_DIR
        claude_skills_dir = CLAUDE_DIR / "skills"
    if agent_tools_skills_dir is None:
        from ..lib import AGENT_TOOLS_DIR
        agent_tools_skills_dir = AGENT_TOOLS_DIR / "skills"

    targets = [
        claude_skills_dir / "agents-environment-config",
        agent_tools_skills_dir / "agents-environment-config",
    ]

    for link_path in targets:
        if not link_path.is_symlink():
            continue
        resolved = str(link_path.resolve())
        if "agent-tools" in resolved or "agents-environment-config" in resolved:
            if dry_run:
                Console.info(f"Would remove legacy symlink: {link_path}")
            else:
                link_path.unlink()
                Console.success(f"Cleaned up legacy symlink: {link_path}")


def _find_projects(projects_dir: Path, git_only: bool = True) -> list[Path]:
    """Find project directories in the projects root."""
    if not projects_dir.is_dir():
        return []

    results = []
    for item in sorted(projects_dir.iterdir()):
        if not item.is_dir():
            continue
        if item.name.startswith("."):
            continue
        if git_only and not (item / ".git").is_dir():
            continue
        results.append(item)

    return results


def _batch_project_setup(dry_run: bool = False) -> None:
    """Walk projects directory and offer to setup each one.

    Args:
        dry_run: If True, list projects that would be set up without prompting.
    """
    from ..lib.preferences import get_setting

    projects_dir = get_setting("projects_dir")
    if not projects_dir:
        return

    projects_path = Path(projects_dir)
    if not projects_path.is_dir():
        Console.warning(f"Projects directory not found: {projects_dir}")
        return

    if dry_run:
        # In dry-run mode, scan git repos and list what would be set up
        projects = _find_projects(projects_path, git_only=True)

        if not projects:
            Console.info("No projects found.")
            return

        Console.subheader(f"Projects in {projects_dir} ({len(projects)} found):")
        from . import repo
        for project in projects:
            Console.info(f"  Would setup: {project.name}")
        return

    try:
        response = input("\nWould you like to setup your project directories now? (Y/n): ").strip().lower()
    except EOFError:
        response = "n"

    if response == "n":
        return

    Console.print("\nScan for projects:")
    Console.print("  1) Only git repositories (recommended)")
    Console.print("  2) All directories")
    try:
        scan_choice = input("Choice [1]: ").strip() or "1"
    except EOFError:
        scan_choice = "1"

    git_only = scan_choice != "2"
    projects = _find_projects(projects_path, git_only=git_only)

    if not projects:
        Console.info("No projects found.")
        return

    Console.print(f"\nFound {len(projects)} project(s):\n")

    from . import repo

    for i, project in enumerate(projects):
        if i > 0:
            Console.print(f"\n  {Console.dim('─' * 40)}")
        try:
            response = input(f"\n  Setup {project.name}? (Y/n/q): ").strip().lower()
        except EOFError:
            response = "n"

        if response == "q":
            Console.info("Stopped project setup.")
            break
        if response == "n":
            continue

        repo.setup(str(project), skip_raycast=True, batch=True)


def _prompt_settings(dry_run: bool = False, show_header: bool = True) -> None:
    """Prompt for settings if not already configured.

    In dry-run mode, the user walks through the same prompts interactively
    but answers are reported as "Would save" instead of persisted to disk.
    Already-configured settings are shown as-is and not re-prompted.

    Args:
        dry_run: If True, run prompts but don't persist answers.
        show_header: If True, print a subheader before prompts.
    """
    from ..lib.preferences import get_setting, set_setting
    from ..lib import get_projects_dir

    # Check if all settings are already set
    required_settings = ["projects_dir", "plans_dir", "plans_gitignored", "plans_completion"]

    if not dry_run and all(get_setting(k) is not None for k in required_settings):
        return

    if show_header:
        Console.subheader("Configuration")

    # Helper: persist or report based on dry_run
    # In dry-run mode, keep an in-memory dict so later prompts can reference
    # earlier answers (e.g. plans_dir prompt references projects_dir answer)
    dry_run_settings: dict[str, object] = {}

    def _save(key: str, value: object) -> None:
        if dry_run:
            dry_run_settings[key] = value
            Console.info(f"Would save: {key} = {value}")
        else:
            set_setting(key, value)

    def _get(key: str) -> object:
        """Get a setting, checking dry-run in-memory values first."""
        if dry_run and key in dry_run_settings:
            return dry_run_settings[key]
        return get_setting(key)

    # 1. Projects directory
    current = get_setting("projects_dir")
    if current is not None:
        if dry_run:
            Console.success(f"projects_dir = {current}")
    else:
        default_dir = str(get_projects_dir())
        try:
            response = input(f"Where is your projects root directory? [{default_dir}]: ").strip()
        except EOFError:
            response = ""
        projects_dir = response or default_dir
        _save("projects_dir", str(Path(projects_dir).expanduser().resolve()))

    # 2. Plans directory
    current = get_setting("plans_dir")
    if current is not None:
        if dry_run:
            Console.success(f"plans_dir = {current}")
    else:
        Console.print("\nWhere should plan files go in your projects?")
        Console.print("  1) .plans/ (recommended)")
        Console.print("  2) plans/")
        Console.print("  3) Other (type your own)")
        try:
            response = input("Choice [1]: ").strip() or "1"
        except EOFError:
            response = "1"

        if response == "1":
            _save("plans_dir", ".plans")
        elif response == "2":
            _save("plans_dir", "plans")
        else:
            if response == "3":
                try:
                    custom = input("Plans directory name: ").strip() or ".plans"
                except EOFError:
                    custom = ".plans"
            else:
                custom = response  # user typed the name directly
            _save("plans_dir", custom)

    # 3. Plans gitignored
    current = get_setting("plans_gitignored")
    if current is not None:
        if dry_run:
            Console.success(f"plans_gitignored = {current}")
    else:
        plans_dir = _get("plans_dir")
        try:
            response = input(f"Should {plans_dir}/ be tracked in git? (y/N): ").strip().lower()
        except EOFError:
            response = "n"
        tracked = response in ("y", "yes")
        _save("plans_gitignored", not tracked)

    # 4. Plans completion behavior
    current = get_setting("plans_completion")
    if current is not None:
        if dry_run:
            Console.success(f"plans_completion = {current}")
    else:
        plans_dir = _get("plans_dir")
        Console.print(f"\nWhen a plan is completed, should the agent:")
        Console.print(f"  1) Archive to {plans_dir}/archive/ (recommended)")
        Console.print(f"  2) Delete the plan file")
        try:
            response = input("Choice [1]: ").strip() or "1"
        except EOFError:
            response = "1"
        _save("plans_completion", "archive" if response == "1" else "delete")


def _prompt_configurable_instructions(dry_run: bool = False) -> None:
    """Prompt user to configure per-agent instruction toggles.

    Checks each configurable instruction. If not yet configured, shows
    the prompt and lets the user choose per agent. If already configured,
    skips silently.

    Args:
        dry_run: If True, report what would happen without persisting.
    """
    from ..lib.configurable_instructions import (
        CONFIGURABLE_INSTRUCTIONS,
        get_all_agent_keys,
        get_agent_display_name,
        apply_instruction_config,
        scan_file_for_instruction,
        get_agent_global_file,
    )
    from ..lib.preferences import (
        is_instruction_configured,
        set_instruction_config,
    )
    from ..lib.tracking import list_repos as tracking_list_repos

    for key, instruction in CONFIGURABLE_INSTRUCTIONS.items():
        if is_instruction_configured(key):
            Console.success(f"{instruction['description']} (already configured)")
            continue

        # Show the prompt
        Console.print(instruction["prompt"])

        agent_keys = get_all_agent_keys()
        agent_configs = {}

        # Check which agents currently have the instruction
        for agent_key in agent_keys:
            display = get_agent_display_name(agent_key)
            global_file = get_agent_global_file(agent_key)
            has_it = False
            if global_file:
                has_it = scan_file_for_instruction(global_file, key)

            default = "Y" if instruction["default_enabled"] else "n"
            if has_it:
                hint = " (currently present)"
            else:
                hint = ""

            try:
                response = input(
                    f"  Keep for {display}?{hint} ({default}/{'n' if default == 'Y' else 'Y'}): "
                ).strip().lower()
            except EOFError:
                response = ""

            if response == "":
                enabled = instruction["default_enabled"]
            elif response in ("y", "yes"):
                enabled = True
            elif response in ("n", "no"):
                enabled = False
            else:
                enabled = instruction["default_enabled"]

            agent_configs[agent_key] = enabled

        if dry_run:
            Console.info("Would save configurable instruction preferences:")
            for agent_key, enabled in agent_configs.items():
                display = get_agent_display_name(agent_key)
                status = "keep" if enabled else "remove"
                Console.info(f"  {display}: {status}")
        else:
            set_instruction_config(key, agent_configs)

            # Apply changes to all tracked repos
            tracked = tracking_list_repos()
            repo_paths = [r.path for r in tracked if r.exists]

            results = apply_instruction_config(
                key, agent_configs, repo_paths, dry_run=False
            )

            if results["removed"]:
                Console.success(
                    f"Removed instruction from {len(results['removed'])} file(s)"
                )
            if results["added"]:
                Console.success(
                    f"Added instruction to {len(results['added'])} file(s)"
                )
            if not results["removed"] and not results["added"]:
                Console.info("No changes needed")

        Console.print()


def _prompt_quality_settings(dry_run: bool = False) -> None:
    """Prompt for quality infrastructure settings.

    Handles port registry and scheduled test configuration. When scheduled
    tests are enabled, also prompts for report viewer and retention policy.

    Args:
        dry_run: If True, report what would happen without persisting.
    """
    from ..lib.preferences import get_preference, set_setting

    Console.subheader("Quality Infrastructure")

    # Helper: persist or report based on dry_run
    def _save(key: str, value: object) -> None:
        if dry_run:
            Console.info(f"Would save: {key} = {value}")
        else:
            set_setting(key, value)

    # Check if scheduled tests are enabled (from OPTIONAL_FEATURES prompt)
    scheduled_enabled = get_preference("scheduled_tests_enabled")
    if not scheduled_enabled:
        Console.info("Scheduled tests not enabled — skipping viewer/retention prompts.")
        return

    # Report viewer selection
    viewer_value = None
    try:
        from aec.lib.viewers import detect_viewers  # type: ignore[import-not-found]

        viewers = detect_viewers()
        if viewers:
            Console.print("\nAvailable report viewers:")
            for i, viewer in enumerate(viewers, 1):
                Console.print(f"  {i}) {viewer['display_name']}")
            Console.print(f"  {len(viewers) + 1}) None")
            try:
                choice = input("Choose a viewer [1]: ").strip() or "1"
            except EOFError:
                choice = "1"
            try:
                idx = int(choice) - 1
            except ValueError:
                idx = 0
            if 0 <= idx < len(viewers):
                viewer_value = viewers[idx]["key"]
        else:
            viewer_value = None
    except ImportError:
        Console.print(
            "\nEnter a command to open test reports (use {file} as placeholder),\n"
            'or "none" to skip:'
        )
        try:
            cmd = input("Viewer command [none]: ").strip() or "none"
        except EOFError:
            cmd = "none"
        if cmd.lower() != "none":
            viewer_value = cmd

    _save("report_viewer", viewer_value)

    # Report retention mode
    Console.print(
        "\nHow should test reports be managed?\n"
        "  1. Automatically prune after N days (default: 30)\n"
        "  2. Manage manually"
    )
    try:
        retention_choice = input("Choice (1/2): ").strip() or "1"
    except EOFError:
        retention_choice = "1"

    if retention_choice == "1":
        _save("report_retention_mode", "auto")
        try:
            days_str = input("Prune reports after how many days? [30]: ").strip() or "30"
        except EOFError:
            days_str = "30"
        try:
            days = int(days_str)
        except ValueError:
            days = 30
        _save("report_retention_days", days)
    else:
        _save("report_retention_mode", "manual")


def install(dry_run: bool = False) -> None:
    """
    Full setup of agents-environment-config.

    This command:
    1. Initializes ~/.agents-environment-config/
    2. Updates git submodules (agents, skills)
    3. Generates .agent-rules/ from .cursor/rules/
    4. Sets up ~/.agent-tools/ structure

    Args:
        dry_run: If True, report what would happen without making changes.
    """
    Console.header("Agents Environment Config Setup")

    if dry_run:
        Console.warning("DRY RUN MODE - No changes will be made\n")

    repo_root = get_repo_root()
    if not repo_root:
        Console.error("Could not find agents-environment-config repository")
        Console.print("Make sure you're running this from within the repo or it's properly installed.")
        raise SystemExit(1)

    Console.print(f"Repository: {Console.path(repo_root)}")

    # Initialize AEC home directory
    with Console.section("Initializing configuration directory...", collapse=not dry_run):
        init_aec_home(dry_run)
        if not dry_run:
            Console.success("~/.agents-environment-config/ initialized")

    # Update submodules
    if is_git_repo(repo_root) and has_gitmodules(repo_root):
        with Console.section("Updating submodules...", collapse=not dry_run):
            # Initialize submodules
            success, message = init_submodules(repo_root, dry_run)
            if success:
                Console.success(message)
            else:
                Console.warning(f"Submodule init: {message}")

            # Update each submodule defined in sync-config.json
            _update_submodules_from_config(repo_root, dry_run)
    else:
        Console.info("Not a git repository or no submodules - skipping submodule update")

    # Generate .agent-rules/
    with Console.section("Generating .agent-rules/ directory...", collapse=not dry_run):
        cursor_rules = repo_root / ".cursor" / "rules"
        if cursor_rules.exists():
            rules.generate(dry_run)
        else:
            Console.warning(".cursor/rules/ not found - skipping rule generation")

    # Setup agent-tools
    with Console.section("Setting up ~/.agent-tools/ structure...", collapse=not dry_run):
        agent_tools.setup(dry_run)

    # Clean up legacy skill symlinks
    with Console.section("Cleaning up legacy symlinks...", collapse=not dry_run):
        _cleanup_legacy_symlinks(dry_run=dry_run)
        if not dry_run:
            Console.success("Legacy symlink cleanup complete")

    # Skills install/update step
    with Console.section("Skills management...", collapse=False):
        from . import skills
        skills.install_step(dry_run=dry_run)

    # Detect and display agents
    with Console.section("Detecting installed agents...", collapse=not dry_run):
        from ..lib import detect_agents
        detected = detect_agents()
        if detected:
            agent_names = ", ".join(detected.keys())
            Console.success(f"Found: {agent_names}")
            if not dry_run:
                Console.print("  During project setup, we'll create instruction files for these agents.")
        else:
            Console.warning("No supported agents detected.")

    # Prompt for settings (interactive — never collapse)
    with Console.section("Configuration", collapse=False):
        _prompt_settings(dry_run, show_header=False)

    # Quality infrastructure preferences (interactive — never collapse)
    with Console.section("Quality Infrastructure", collapse=False):
        _prompt_quality_settings(dry_run)

    # Regenerate rules with new settings applied
    with Console.section("Applying settings to rules...", collapse=not dry_run):
        if not dry_run:
            cursor_rules_dir = repo_root / ".cursor" / "rules"
            if cursor_rules_dir.exists():
                rules.generate()
        else:
            Console.info("Would regenerate rules with applied settings")

    # Repair hook key casing in all tracked repos
    with Console.section("Repairing hook configurations...", collapse=not dry_run):
        from ..lib.tracking import list_repos as tracking_list_repos
        from ..lib.hooks import repair_hook_keys, AGENT_HOOK_CONFIGS

        tracked = tracking_list_repos()
        fixed_count = 0
        for repo in tracked:
            if not repo.exists:
                continue
            if dry_run:
                results = repair_hook_keys(repo.path)
                for agent_key, status in results.items():
                    if status == "fixed":
                        Console.warning(
                            f"Would fix hook key casing: {repo.path.name}/{AGENT_HOOK_CONFIGS[agent_key]['config_path']}"
                        )
                        fixed_count += 1
            else:
                results = repair_hook_keys(repo.path)
                for agent_key, status in results.items():
                    if status == "fixed":
                        Console.success(
                            f"Fixed hook key casing: {repo.path.name}/{AGENT_HOOK_CONFIGS[agent_key]['config_path']}"
                        )
                        fixed_count += 1

        if fixed_count == 0:
            Console.success("All hook configs use correct key casing")
        elif dry_run:
            Console.info(f"Would fix {fixed_count} hook config(s)")

    # Configure per-agent instructions (interactive — never collapse)
    with Console.section("Configurable Instructions", collapse=False):
        _prompt_configurable_instructions(dry_run)

    # Batch project setup (interactive — never collapse)
    _batch_project_setup(dry_run)

    # Final summary
    if dry_run:
        Console.header("DRY RUN COMPLETE")
        Console.warning("No changes were made.")
        Console.print("\nRun without --dry-run to apply changes.")
    else:
        Console.header("Setup Complete")
        Console.success("All components installed successfully!")
        Console.print()
        Console.print("What was set up:")
        Console.print(f"  - ~/.agents-environment-config/  (local config)")
        Console.print(f"  - ~/.agent-tools/                (shared agent content)")
        Console.print(f"  - ~/.claude/skills/              (installed skills)")
        Console.print(f"  - .agent-rules/                  (frontmatter-stripped rules)")
        Console.print()
        Console.print("Next steps:")
        Console.print(f"  1. Setup a project: {Console.cmd('aec repo setup <project>')}")
        Console.print(f"  2. Manage skills:   {Console.cmd('aec skills list')}")
        Console.print(f"  3. Check health:    {Console.cmd('aec doctor')}")
        Console.print()
