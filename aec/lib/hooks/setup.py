"""Interactive resource setup shared by every hook-bearing item.

The prompt registry owns unattended answers; hooks.json owns which directories
are resources to create. Predicates remain detection, never mkdir instructions.
"""
from copy import deepcopy
import json
from pathlib import Path
import shlex

from ..atomic_write import atomic_write_json
from ..console import Console
from ..prompts import prompt
from ..prompt_catalog.install_flow_area import (
    INSTALL_DIRECTORY_PREFIX, INSTALL_HOOKS_ENABLE_PREFIX, item_prompt_id,
)

DIRECTORIES_FILE = ".aec/directories.json"


def validate_directory(value: str, repo_root: Path) -> str:
    if not isinstance(value, str):
        raise ValueError("directory must be a string")
    path = Path(value)
    if (not value or path.is_absolute() or ".." in path.parts
            or "\\" in value or value == "." or any(ord(c) < 32 for c in value)):
        raise ValueError("choose a relative directory inside the repository")
    target = repo_root / path
    if not target.resolve().is_relative_to(repo_root.resolve()):
        raise ValueError("directory must stay inside the repository, including symlinks")
    if target.exists() and not target.is_dir():
        raise ValueError(f"{value} is a file, not a directory")
    return path.as_posix()


def configure_directories(directories: dict, repo_root: Path, *, assume_yes=False) -> dict:
    """Resolve, create, and persist shared resource locations before enabling hooks."""
    config_path = repo_root / DIRECTORIES_FILE
    configured = json.loads(config_path.read_text()) if config_path.exists() else {}
    if not isinstance(configured, dict):
        raise ValueError(f"{DIRECTORIES_FILE} must contain a directory mapping")
    chosen = {}
    for name, default in directories.items():
        default = configured.get(name, default)
        value = prompt(
            item_prompt_id(INSTALL_DIRECTORY_PREFIX, name),
            f"Directory for {name} [{default}]: ",
            type="path", default=default,
            use_default=assume_yes or name in configured,
            validator=lambda value: validate_directory(value, repo_root),
        )
        chosen[name] = validate_directory(value, repo_root)
    # Validate every answer before creating any directories.
    for value in chosen.values():
        (repo_root / value).mkdir(parents=True, exist_ok=True)
    if chosen:
        atomic_write_json(config_path, {**configured, **chosen})
    return chosen


def configure_install(hf, repo_root, state, *, assume_yes=False):
    configure_directories(hf.directories, repo_root, assume_yes=assume_yes)
    enabled_default = state.hooks_enabled if state.hooks_enabled is not None else True
    from ..prompts import yes_no_hint
    state.hooks_enabled = prompt(
        item_prompt_id(INSTALL_HOOKS_ENABLE_PREFIX, f"{state.item_type}.{state.item_key}"),
        f"Install hooks for {state.item_key}? {yes_no_hint(enabled_default)}: ",
        type="yes_no", default=enabled_default,
        # Pre-choice state records came from an explicit hook installation.
        # Preserve that consent during upgrade/repair rather than prompting again.
        use_default=assume_yes or state.hooks_enabled is not None or bool(state.item_version),
    ) == "y"
    if state.hooks_enabled is False:
        Console.info(f"{state.item_key}: hooks disabled by your saved choice; directories are ready.")
    return configured_hooks(hf, repo_root, state)


def configured_hooks(hf, repo_root, state):
    """Render saved choices without prompting or writing (also used by doctor)."""
    config_path = repo_root / DIRECTORIES_FILE
    configured = json.loads(config_path.read_text()) if config_path.exists() else {}
    chosen = {name: validate_directory(configured.get(name, default), repo_root)
              for name, default in hf.directories.items()}
    result = deepcopy(hf)
    if state.hooks_enabled is False:
        result.hooks = []
        result.claude = result.cursor = result.gemini = result.git = []
        return result
    for hook in result.hooks:
        for name, default in hf.directories.items():
            selected = chosen[name]
            hook.command = hook.command.replace("{directory:" + name + "}", shlex.quote(selected))
            if hook.when:
                for field in ("repo_has", "repo_has_any", "repo_lacks"):
                    paths = getattr(hook.when, field)
                    setattr(hook.when, field, [
                        selected + path[len(default):]
                        if path == default or path.startswith(default + "/") else path
                        for path in paths
                    ])
    return result
