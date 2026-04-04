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
    prune_stale,
    untrack_repo,
    discover_from_scripts,
    TrackedRepo,
)
from .preferences import (
    OPTIONAL_FEATURES,
    load_preferences,
    save_preferences,
    get_preference,
    set_preference,
    reset_preference,
    get_setting,
    set_setting,
    get_pending_prompts,
    check_pending_preferences,
    get_instruction_config,
    set_instruction_config,
    is_instruction_configured,
)
from .configurable_instructions import (
    CONFIGURABLE_INSTRUCTIONS,
    apply_instruction_config,
    get_all_agent_keys,
    get_agent_display_name,
    scan_file_for_instruction,
    get_agent_global_file,
)
from .hooks import (
    LANGUAGE_HOOKS,
    AGENT_HOOK_CONFIGS,
    detect_languages,
    generate_hook_config,
    write_hook_config,
)
from .version_check import (
    check_for_update,
    print_update_banner,
    maybe_check_for_update,
)
from .agent_files import (
    generate_all as generate_agent_files,
    generate_agent_file,
    organize_rules,
)
from .skills_manifest import (
    parse_skill_frontmatter,
    parse_version,
    version_is_newer,
    hash_skill_directory,
    load_installed_manifest,
    save_installed_manifest,
    discover_available_skills,
    rebuild_manifest_from_installed,
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
    "prune_stale",
    "untrack_repo",
    "discover_from_scripts",
    "TrackedRepo",
    # Preferences
    "OPTIONAL_FEATURES",
    "load_preferences",
    "save_preferences",
    "get_preference",
    "set_preference",
    "reset_preference",
    "get_setting",
    "set_setting",
    "get_pending_prompts",
    "check_pending_preferences",
    "get_instruction_config",
    "set_instruction_config",
    "is_instruction_configured",
    # Configurable instructions
    "CONFIGURABLE_INSTRUCTIONS",
    "apply_instruction_config",
    "get_all_agent_keys",
    "get_agent_display_name",
    "scan_file_for_instruction",
    "get_agent_global_file",
    # Hooks
    "LANGUAGE_HOOKS",
    "AGENT_HOOK_CONFIGS",
    "detect_languages",
    "generate_hook_config",
    "write_hook_config",
    # Version check
    "check_for_update",
    "print_update_banner",
    "maybe_check_for_update",
    # Agent files
    "generate_agent_files",
    "generate_agent_file",
    "organize_rules",
    # Skills manifest
    "parse_skill_frontmatter",
    "parse_version",
    "version_is_newer",
    "hash_skill_directory",
    "load_installed_manifest",
    "save_installed_manifest",
    "discover_available_skills",
    "rebuild_manifest_from_installed",
]
