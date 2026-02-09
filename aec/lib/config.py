"""Platform-aware configuration and paths."""

import os
import platform
import shutil
from pathlib import Path
from typing import Optional

# Version
VERSION = "2.0.0"

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

# Home directory
HOME = Path.home()

# AEC local configuration directory
AEC_HOME = HOME / ".agents-environment-config"
AEC_SETUP_LOG = AEC_HOME / "setup-repo-locations.txt"
AEC_README = AEC_HOME / "README.md"

# Agent tools directory (shared across agents)
AGENT_TOOLS_DIR = HOME / ".agent-tools"

# Agent-specific directories
CLAUDE_DIR = HOME / ".claude"
CURSOR_DIR = HOME / ".cursor"

# Supported agents with detection and launch configuration
SUPPORTED_AGENTS = {
    "claude": {
        "commands": ["claude"],
        "alt_paths": [HOME / ".claude"],
        "terminal_launch": True,
        "launch_args": "--dangerously-skip-permissions",
        "has_resume": True,
        "resume_args": "--dangerously-skip-permissions --resume",
    },
    "cursor": {
        "commands": ["cursor"],
        "alt_paths": [Path("/Applications/Cursor.app")],
        "terminal_launch": False,
        "launch_template": "cursor {path}/",
        "has_resume": False,
    },
    "gemini": {
        "commands": ["gemini"],
        "alt_paths": [],
        "terminal_launch": True,
        "launch_args": "",
        "has_resume": False,
    },
    "qwen": {
        "commands": ["qwen"],
        "alt_paths": [],
        "terminal_launch": True,
        "launch_args": "",
        "has_resume": False,
    },
    "codex": {
        "commands": ["codex"],
        "alt_paths": [],
        "terminal_launch": True,
        "launch_args": "",
        "has_resume": False,
    },
}


def detect_agents() -> dict[str, dict]:
    """
    Detect which supported agents are installed on the system.

    Checks both command availability (via shutil.which) and alternative
    filesystem paths for each agent.

    Returns:
        Dictionary of agent_name -> agent_config for all detected agents.
    """
    detected = {}
    for name, config in SUPPORTED_AGENTS.items():
        found = False

        # Check if the command is available on PATH
        for cmd in config["commands"]:
            if shutil.which(cmd) is not None:
                found = True
                break

        # Check alternative filesystem paths if command not found
        if not found:
            for alt_path in config.get("alt_paths", []):
                if alt_path.exists():
                    found = True
                    break

        if found:
            detected[name] = config

    return detected


def generate_raycast_script(
    agent_name: str,
    agent_config: dict,
    project_name: str,
    project_path: str,
    is_resume: bool = False,
) -> str:
    """
    Generate the contents of a Raycast launcher script for an agent/project.

    Args:
        agent_name: Name of the agent (e.g., "claude", "cursor").
        agent_config: Configuration dict from SUPPORTED_AGENTS.
        project_name: Human-readable project name.
        project_path: Absolute path to the project directory.
        is_resume: Whether to generate the resume variant (claude only).

    Returns:
        The full script content as a string.
    """
    title_suffix = f" {project_name} resume" if is_resume else f" {project_name}"
    desc_suffix = " resume" if is_resume else ""

    header = (
        f"#!/bin/bash\n"
        f"\n"
        f"# Required parameters:\n"
        f"# @raycast.schemaVersion 1\n"
        f"# @raycast.title {agent_name}{title_suffix}\n"
        f"# @raycast.mode compact\n"
        f"\n"
        f"# Optional parameters:\n"
        f"# @raycast.icon 🤖\n"
        f"\n"
        f"# Documentation:\n"
        f"# @raycast.description open {agent_name} {project_name} project{desc_suffix}\n"
        f"# @raycast.author matt_bernier\n"
        f"# @raycast.authorURL https://raycast.com/matt_bernier\n"
    )

    if agent_config.get("terminal_launch", True):
        args = agent_config.get("launch_args", "")
        if is_resume:
            args = agent_config.get("resume_args", args)
        args_str = f" {args}" if args else ""
        command = (
            f"\nosascript -e "
            f"'tell application \"Terminal\" to do script "
            f"\"cd {project_path}/; {agent_name}{args_str}\"'\n"
        )
    else:
        template = agent_config.get("launch_template", f"{agent_name} {{path}}/")
        command = f"\n{template.format(path=project_path)}\n"

    return header + command


# Cached repo root
_repo_root: Optional[Path] = None


def get_repo_root() -> Optional[Path]:
    """
    Find the agents-environment-config repository root.

    Searches upward from the current file location for the repo root,
    identified by the presence of key files/directories.
    """
    global _repo_root

    if _repo_root is not None:
        return _repo_root

    # Start from this file's location
    current = Path(__file__).resolve().parent

    # Walk up looking for repo markers
    for _ in range(10):  # Max 10 levels up
        # Check for repo markers
        if (current / ".agent-rules").is_dir() and (current / "aec").is_dir():
            _repo_root = current
            return _repo_root

        # Also check for .git with our specific structure
        if (current / ".git").exists() and (current / "CLAUDE.md").exists():
            _repo_root = current
            return _repo_root

        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent

    return None


def get_projects_dir() -> Path:
    """
    Get the default projects directory.

    Respects PROJECTS_DIR environment variable if set.
    Falls back to platform-specific conventions.
    """
    env_dir = os.environ.get("PROJECTS_DIR")
    if env_dir:
        return Path(env_dir)

    # Platform conventions
    if IS_WINDOWS:
        # Check common Windows locations
        for name in ["Projects", "projects", "repos", "Repos"]:
            candidate = HOME / name
            if candidate.exists():
                return candidate
        return HOME / "Projects"  # Windows convention
    else:
        # Unix convention
        return HOME / "projects"


def get_github_orgs() -> list[str]:
    """
    Get list of GitHub organizations to search when cloning.

    Respects GITHUB_ORGS environment variable (comma-separated).
    """
    env_orgs = os.environ.get("GITHUB_ORGS", "")
    if env_orgs:
        return [org.strip() for org in env_orgs.split(",") if org.strip()]
    return ["mbernier", "bernierllc"]


def load_env_file(env_path: Optional[Path] = None) -> None:
    """
    Load environment variables from a .env file.

    Args:
        env_path: Path to .env file. If None, looks for .env in repo root.
    """
    if env_path is None:
        repo_root = get_repo_root()
        if repo_root:
            env_path = repo_root / ".env"

    if env_path and env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ.setdefault(key, value)
