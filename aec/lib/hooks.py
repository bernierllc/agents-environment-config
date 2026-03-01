"""Lint hook configuration for AI agent repo setup."""

import json
from pathlib import Path
from typing import Any, Dict, List

LANGUAGE_HOOKS: Dict[str, Dict[str, Any]] = {
    "typescript": {
        "display_name": "TypeScript",
        "detect_files": ["tsconfig.json"],
        "command": "npx tsc --noEmit --pretty 2>&1 | head -20",
    },
    "rust": {
        "display_name": "Rust",
        "detect_files": ["Cargo.toml"],
        "command": "cargo check 2>&1 | head -20",
    },
    "python": {
        "display_name": "Python",
        "detect_files": ["pyproject.toml", "setup.py", "mypy.ini"],
        "command": "mypy . 2>&1 | head -20",
    },
    "go": {
        "display_name": "Go",
        "detect_files": ["go.mod"],
        "command": "go vet ./... 2>&1 | head -20",
    },
    "ruby": {
        "display_name": "Ruby",
        "detect_files": ["Gemfile"],
        "command": "bundle exec rubocop 2>&1 | head -20",
    },
}


def detect_languages(project_dir: Path) -> List[str]:
    """Detect programming languages in a project directory.

    Scans for language-specific config files (tsconfig.json, Cargo.toml, etc.)
    and returns a list of detected language keys.

    Args:
        project_dir: Path to the project root directory.

    Returns:
        List of language keys (e.g., ["typescript", "python"]).
    """
    detected = []
    for lang_key, lang_config in LANGUAGE_HOOKS.items():
        for detect_file in lang_config["detect_files"]:
            if (project_dir / detect_file).exists():
                detected.append(lang_key)
                break
    return detected


AGENT_HOOK_CONFIGS: Dict[str, Dict[str, Any]] = {
    "claude": {
        "config_path": ".claude/settings.json",
        "config_format": "json",
        "template": lambda commands: {
            "hooks": {
                "PostToolUse": [{
                    "matcher": "Edit|Write",
                    "hooks": [
                        {"type": "command", "command": cmd}
                        for cmd in commands
                    ],
                }],
            },
        },
    },
    "gemini": {
        "config_path": ".gemini/settings.json",
        "config_format": "json",
        "template": lambda commands: {
            "tools": {"enableHooks": True},
            "hooks": {
                "enabled": True,
                "AfterTool": [{
                    "matcher": "write_file|replace",
                    "hooks": [
                        {"type": "command", "command": cmd, "name": f"lint-{i}"}
                        for i, cmd in enumerate(commands)
                    ],
                }],
            },
        },
    },
    "cursor": {
        "config_path": ".cursor/hooks.json",
        "config_format": "json",
        "template": lambda commands: {
            "version": 1,
            "hooks": {
                "afterFileEdit": [
                    {"command": cmd} for cmd in commands
                ],
            },
        },
    },
}


def generate_hook_config(agent_key: str, commands: List[str]) -> Dict[str, Any]:
    """Generate hook configuration for a specific agent.

    Args:
        agent_key: Agent identifier (e.g., "claude", "gemini", "cursor").
        commands: List of lint/check commands to run after file edits.

    Returns:
        Dict representing the complete agent hook config.

    Raises:
        KeyError: If agent_key is not in AGENT_HOOK_CONFIGS.
    """
    agent_config = AGENT_HOOK_CONFIGS[agent_key]
    return agent_config["template"](commands)


def write_hook_config(
    project_dir: Path,
    agent_key: str,
    commands: List[str],
    mode: str = "auto",
) -> str:
    """Write hook configuration to the agent's config file.

    Args:
        project_dir: Path to the project root directory.
        agent_key: Agent identifier (e.g., "claude").
        commands: List of lint commands.
        mode: How to handle existing files:
            - "auto": create if missing, return "exists" if file exists
            - "skip": don't modify existing file
            - "merge": add hooks to existing config, preserve other keys
            - "show": don't write, just signal to caller to display config

    Returns:
        Status string: "created", "merged", "skipped", "show", or "exists".
    """
    agent_config = AGENT_HOOK_CONFIGS[agent_key]
    config_path = project_dir / agent_config["config_path"]
    new_config = generate_hook_config(agent_key, commands)

    if config_path.exists():
        if mode == "skip":
            return "skipped"
        if mode == "show":
            return "show"
        if mode == "merge":
            existing = json.loads(config_path.read_text())
            existing.update(new_config)
            config_path.write_text(json.dumps(existing, indent=2) + "\n")
            return "merged"
        # mode == "auto" and file exists
        return "exists"

    # File doesn't exist — create it
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(new_config, indent=2) + "\n")
    return "created"
