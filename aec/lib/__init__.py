"""Shared utilities for aec CLI."""

from .config import (
    VERSION,
    IS_WINDOWS,
    IS_MACOS,
    IS_LINUX,
    HOME,
    AEC_HOME,
    AEC_SETUP_LOG,
    AGENT_TOOLS_DIR,
    CLAUDE_DIR,
    CURSOR_DIR,
    SUPPORTED_AGENTS,
    detect_agents,
    generate_raycast_script,
    get_repo_root,
    get_projects_dir,
    get_github_orgs,
)
from .console import Console
from .filesystem import (
    create_symlink,
    remove_symlink,
    is_symlink,
    is_our_symlink,
    get_symlink_target,
    ensure_directory,
    copy_file,
)
from .tracking import (
    init_aec_home,
    log_setup,
    is_logged,
    get_version,
    list_repos,
    discover_from_scripts,
    TrackedRepo,
)

__all__ = [
    # Config
    "VERSION",
    "IS_WINDOWS",
    "IS_MACOS",
    "IS_LINUX",
    "HOME",
    "AEC_HOME",
    "AEC_SETUP_LOG",
    "AGENT_TOOLS_DIR",
    "CLAUDE_DIR",
    "CURSOR_DIR",
    "SUPPORTED_AGENTS",
    "detect_agents",
    "generate_raycast_script",
    "get_repo_root",
    "get_projects_dir",
    "get_github_orgs",
    # Console
    "Console",
    # Filesystem
    "create_symlink",
    "remove_symlink",
    "is_symlink",
    "is_our_symlink",
    "get_symlink_target",
    "ensure_directory",
    "copy_file",
    # Tracking
    "init_aec_home",
    "log_setup",
    "is_logged",
    "get_version",
    "list_repos",
    "discover_from_scripts",
    "TrackedRepo",
]
