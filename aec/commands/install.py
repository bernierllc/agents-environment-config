"""Install command: aec install - Full setup of agents-environment-config."""

from pathlib import Path

try:
    import typer
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False

from ..lib import Console, get_repo_root, init_aec_home
from ..lib.git import is_git_repo, has_gitmodules, init_submodules, update_submodule
from . import agent_tools, rules


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

            # Update agents submodule
            agents_path = ".claude/agents"
            if (repo_root / agents_path).exists():
                Console.print("  Updating agents...")
                success, result = update_submodule(repo_root, agents_path, dry_run)
                if success:
                    Console.success(f"Agents updated to {result}")
                else:
                    Console.warning(f"Agents: {result}")

            # Update skills submodule
            skills_path = ".claude/skills"
            if (repo_root / skills_path).exists():
                Console.print("  Updating skills...")
                success, result = update_submodule(repo_root, skills_path, dry_run)
                if success:
                    Console.success(f"Skills updated to {result}")
                else:
                    Console.warning(f"Skills: {result}")
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
        Console.print(f"  - .agent-rules/                  (frontmatter-stripped rules)")
        Console.print()
        Console.print("Next steps:")
        Console.print(f"  1. Setup a project: {Console.cmd('python -m aec repo setup <project>')}")
        Console.print(f"  2. Check health:    {Console.cmd('python -m aec doctor')}")
        Console.print()
