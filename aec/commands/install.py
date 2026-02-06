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
