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
    detect_agents,
    generate_raycast_script,
    get_repo_root,
    get_projects_dir,
    get_github_orgs,
)
from .registry import (
    load_agent_registry,
    get_supported_agents,
    get_agent_files,
    get_gitignore_patterns,
    get_migration_files,
    get_generation_agents,
    invalidate_cache,
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

# SUPPORTED_AGENTS is lazy-loaded via config.__getattr__
# Import it explicitly for backwards compatibility
SUPPORTED_AGENTS = get_supported_agents()

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
    # Registry
    "load_agent_registry",
    "get_supported_agents",
    "get_agent_files",
    "get_gitignore_patterns",
    "get_migration_files",
    "get_generation_agents",
    "invalidate_cache",
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
