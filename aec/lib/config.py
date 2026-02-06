"""Platform-aware configuration and paths."""

import os
import platform
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
