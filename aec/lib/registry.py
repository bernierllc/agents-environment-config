"""Agent registry loader - single source of truth from agents.json."""

import json
from pathlib import Path
from typing import Optional


# Cached registry data
_registry_cache: Optional[dict] = None


def _find_agents_json() -> Optional[Path]:
    """Find agents.json by walking up from this file's location."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        candidate = current / "agents.json"
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def load_agent_registry() -> dict:
    """Load and cache the agent registry from agents.json.

    Returns the full registry dict. Returns empty registry if agents.json
    is not found (e.g. pip-installed without repo).
    """
    global _registry_cache

    if _registry_cache is not None:
        return _registry_cache

    agents_json = _find_agents_json()
    if agents_json is None:
        _registry_cache = {"agents": {}}
        return _registry_cache

    with open(agents_json) as f:
        _registry_cache = json.load(f)

    return _registry_cache


def get_supported_agents() -> dict:
    """Return a dict matching the shape of the old SUPPORTED_AGENTS.

    Each agent entry has: commands, alt_paths (as Path objects),
    terminal_launch, launch_args, has_resume, and optionally
    resume_args and launch_template.
    """
    registry = load_agent_registry()
    result = {}

    for name, agent in registry.get("agents", {}).items():
        config: dict = {
            "commands": list(agent["commands"]),
            "alt_paths": [
                Path(p.replace("~", str(Path.home())))
                for p in agent.get("alt_paths", [])
            ],
            "terminal_launch": agent["terminal_launch"],
            "has_resume": agent["has_resume"],
        }

        if agent["terminal_launch"]:
            config["launch_args"] = agent.get("launch_args", "")
        else:
            config["launch_template"] = agent.get(
                "launch_template", f"{name} {{path}}/"
            )

        if agent["has_resume"]:
            config["resume_args"] = agent.get("resume_args", "")

        result[name] = config

    return result


def get_agent_files() -> list[str]:
    """Return the list of agent files to copy during repo setup.

    Always includes AGENTINFO.md plus each agent's instruction_file
    (where not null).
    """
    registry = load_agent_registry()
    files = ["AGENTINFO.md"]

    for agent in registry.get("agents", {}).values():
        instruction_file = agent.get("instruction_file")
        if instruction_file and instruction_file not in files:
            files.append(instruction_file)

    return files


def get_gitignore_patterns() -> list[str]:
    """Return patterns to add to .gitignore in target projects."""
    files = get_agent_files()
    return files + [".cursor/rules", "/plans/"]


def get_migration_files() -> list[str]:
    """Return instruction files that need .agent-rules migration checks.

    Only files where use_agent_rules is True (these reference .agent-rules/).
    """
    registry = load_agent_registry()
    files = []

    for agent in registry.get("agents", {}).values():
        if agent.get("use_agent_rules") and agent.get("instruction_file"):
            files.append(agent["instruction_file"])

    return files


def get_generation_agents() -> dict[str, tuple[str, bool]]:
    """Return {filename: (display_name, use_agent_rules)} for generate-agent-files.py.

    Only includes agents that have an instruction_file.
    """
    registry = load_agent_registry()
    result = {}

    for agent in registry.get("agents", {}).values():
        instruction_file = agent.get("instruction_file")
        if instruction_file:
            result[instruction_file] = (
                agent["display_name"],
                agent.get("use_agent_rules", True),
            )

    return result


def invalidate_cache() -> None:
    """Clear the cached registry. Useful for testing."""
    global _registry_cache
    _registry_cache = None
