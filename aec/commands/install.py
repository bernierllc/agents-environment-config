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


def _batch_project_setup() -> None:
    """Walk projects directory and offer to setup each one."""
    from ..lib.preferences import get_setting

    projects_dir = get_setting("projects_dir")
    if not projects_dir:
        return

    projects_path = Path(projects_dir)
    if not projects_path.is_dir():
        Console.warning(f"Projects directory not found: {projects_dir}")
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

    for project in projects:
        try:
            response = input(f"  Setup {project.name}? (Y/n/q): ").strip().lower()
        except EOFError:
            response = "n"

        if response == "q":
            Console.info("Stopped project setup.")
            break
        if response == "n":
            continue

        repo.setup(str(project), skip_raycast=True, batch=True)


def _prompt_settings() -> None:
    """Prompt for settings if not already configured."""
    from ..lib.preferences import get_setting, set_setting
    from ..lib import get_projects_dir

    # Check if all settings are already set
    required_settings = ["projects_dir", "plans_dir", "plans_gitignored", "plans_completion"]
    if all(get_setting(k) is not None for k in required_settings):
        return

    Console.subheader("Configuration")

    # 1. Projects directory
    if get_setting("projects_dir") is None:
        default_dir = str(get_projects_dir())
        try:
            response = input(f"Where is your projects root directory? [{default_dir}]: ").strip()
        except EOFError:
            response = ""
        projects_dir = response or default_dir
        set_setting("projects_dir", str(Path(projects_dir).expanduser().resolve()))

    # 2. Plans directory
    if get_setting("plans_dir") is None:
        Console.print("\nWhere should plan files go in your projects?")
        Console.print("  1) .plans/ (recommended)")
        Console.print("  2) plans/")
        Console.print("  3) Other (type your own)")
        try:
            response = input("Choice [1]: ").strip() or "1"
        except EOFError:
            response = "1"

        if response == "1":
            set_setting("plans_dir", ".plans")
        elif response == "2":
            set_setting("plans_dir", "plans")
        else:
            if response == "3":
                try:
                    custom = input("Plans directory name: ").strip() or ".plans"
                except EOFError:
                    custom = ".plans"
            else:
                custom = response  # user typed the name directly
            set_setting("plans_dir", custom)

    # 3. Plans gitignored
    if get_setting("plans_gitignored") is None:
        plans_dir = get_setting("plans_dir")
        try:
            response = input(f"Should {plans_dir}/ be tracked in git? (y/N): ").strip().lower()
        except EOFError:
            response = "n"
        tracked = response in ("y", "yes")
        set_setting("plans_gitignored", not tracked)

    # 4. Plans completion behavior
    if get_setting("plans_completion") is None:
        plans_dir = get_setting("plans_dir")
        Console.print(f"\nWhen a plan is completed, should the agent:")
        Console.print(f"  1) Archive to {plans_dir}/archive/ (recommended)")
        Console.print(f"  2) Delete the plan file")
        try:
            response = input("Choice [1]: ").strip() or "1"
        except EOFError:
            response = "1"
        set_setting("plans_completion", "archive" if response == "1" else "delete")


def install() -> None:
    """
    Full setup of agents-environment-config.

    This command:
    1. Initializes ~/.agents-environment-config/
    2. Updates git submodules (agents, skills)
    3. Generates .agent-rules/ from .cursor/rules/
    4. Sets up ~/.agent-tools/ structure
    """
    Console.header("Agents Environment Config Setup")

    repo_root = get_repo_root()
    if not repo_root:
        Console.error("Could not find agents-environment-config repository")
        Console.print("Make sure you're running this from within the repo or it's properly installed.")
        raise SystemExit(1)

    Console.print(f"Repository: {Console.path(repo_root)}")

    # Initialize AEC home directory
    Console.subheader("Initializing configuration directory...")
    init_aec_home()
    Console.success("~/.agents-environment-config/ initialized")

    # Update submodules
    if is_git_repo(repo_root) and has_gitmodules(repo_root):
        Console.subheader("Updating submodules...")

        # Initialize submodules
        success, message = init_submodules(repo_root)
        if success:
            Console.success(message)
        else:
            Console.warning(f"Submodule init: {message}")

        # Update agents submodule
        agents_path = ".claude/agents"
        if (repo_root / agents_path).exists():
            Console.print("  Updating agents...")
            success, result = update_submodule(repo_root, agents_path)
            if success:
                Console.success(f"Agents updated to {result}")
            else:
                Console.warning(f"Agents: {result}")

        # Update skills submodule
        skills_path = ".claude/skills"
        if (repo_root / skills_path).exists():
            Console.print("  Updating skills...")
            success, result = update_submodule(repo_root, skills_path)
            if success:
                Console.success(f"Skills updated to {result}")
            else:
                Console.warning(f"Skills: {result}")
    else:
        Console.info("Not a git repository or no submodules - skipping submodule update")

    # Generate .agent-rules/
    Console.subheader("Generating .agent-rules/ directory...")
    cursor_rules = repo_root / ".cursor" / "rules"
    if cursor_rules.exists():
        rules.generate()
    else:
        Console.warning(".cursor/rules/ not found - skipping rule generation")

    # Setup agent-tools
    Console.subheader("Setting up ~/.agent-tools/ structure...")
    agent_tools.setup()

    # Detect and display agents
    Console.subheader("Detecting installed agents...")
    from ..lib import detect_agents
    detected = detect_agents()
    if detected:
        agent_names = ", ".join(detected.keys())
        Console.success(f"Found: {agent_names}")
        Console.print("  During project setup, we'll create instruction files for these agents.")
    else:
        Console.warning("No supported agents detected.")

    # Prompt for settings
    _prompt_settings()

    # Regenerate rules with new settings applied
    Console.subheader("Applying settings to rules...")
    cursor_rules_dir = repo_root / ".cursor" / "rules"
    if cursor_rules_dir.exists():
        rules.generate()

    # Batch project setup
    _batch_project_setup()

    # Final summary
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
