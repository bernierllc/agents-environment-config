"""Configurable instructions that can be toggled per agent.

Some instructions that AEC historically included in agent files may not be
needed for all agents (e.g., agents with large context windows). This module
manages scanning, adding, and removing those instructions across agent files.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import HOME
from .registry import load_agent_registry


# Registry of configurable instructions.
# Each entry defines:
#   description: Human-readable name
#   prompt: Text shown when asking the user during install/update
#   text: The exact instruction text (may span multiple sentences)
#   section: The markdown section header this instruction lives under (if any)
#   default_enabled: Default value for newly detected agents
CONFIGURABLE_INSTRUCTIONS: Dict[str, Dict] = {
    "session-separation": {
        "description": "Separate planning and implementation sessions",
        "prompt": (
            "Configurable Instruction: Session Separation\n"
            "\n"
            "AEC has historically included this instruction in agent files:\n"
            '  "Do not combine planning and implementation in a single session."\n'
            "\n"
            "Agents with large context windows may not need this constraint.\n"
            "You can configure this per agent -- keeping it where it helps\n"
            "and removing it where it doesn't.\n"
        ),
        "text": (
            "Do not combine planning and implementation in a single session. "
            "If the user asks to plan, produce the plan and stop. "
            "If the user asks to implement, start from an existing plan "
            "and begin coding immediately."
        ),
        # Regex pattern to match the instruction in files (handles line wrapping)
        "pattern": (
            r"-\s*Do not combine planning and implementation in a single session\."
            r"[^\n]*(?:\n[^\n-]*)*?begin coding immediately\."
        ),
        "default_enabled": True,
    },
}


def get_agent_global_file(agent_key: str) -> Optional[Path]:
    """Get the path to an agent's global instruction file.

    Returns the path to e.g. ~/.claude/CLAUDE.md, or None if the agent
    doesn't have alt_paths or an instruction_file.
    """
    registry = load_agent_registry()
    agent = registry.get("agents", {}).get(agent_key)
    if not agent:
        return None

    instruction_file = agent.get("instruction_file")
    if not instruction_file:
        return None

    # Use the first alt_path as the global config directory
    alt_paths = agent.get("alt_paths", [])
    if not alt_paths:
        return None

    # Expand ~ in alt_paths
    global_dir = Path(alt_paths[0].replace("~", str(HOME)))
    return global_dir / instruction_file


def get_agent_project_file(agent_key: str, project_dir: Path) -> Optional[Path]:
    """Get the path to an agent's per-project instruction file."""
    registry = load_agent_registry()
    agent = registry.get("agents", {}).get(agent_key)
    if not agent:
        return None

    instruction_file = agent.get("instruction_file")
    if not instruction_file:
        return None

    return project_dir / instruction_file


def scan_file_for_instruction(
    filepath: Path, instruction_key: str
) -> bool:
    """Check if a file contains a configurable instruction.

    Args:
        filepath: Path to the file to scan.
        instruction_key: Key from CONFIGURABLE_INSTRUCTIONS.

    Returns:
        True if the instruction text is found in the file.
    """
    if not filepath.exists():
        return False

    instruction = CONFIGURABLE_INSTRUCTIONS.get(instruction_key)
    if not instruction:
        return False

    content = filepath.read_text()
    pattern = instruction["pattern"]
    return bool(re.search(pattern, content))


def remove_instruction_from_file(
    filepath: Path, instruction_key: str, dry_run: bool = False
) -> bool:
    """Remove a configurable instruction from a file.

    Removes the matching line(s) and cleans up any resulting empty
    sections or double blank lines.

    Args:
        filepath: Path to the file to modify.
        instruction_key: Key from CONFIGURABLE_INSTRUCTIONS.
        dry_run: If True, don't modify the file.

    Returns:
        True if the instruction was found (and removed if not dry_run).
    """
    if not filepath.exists():
        return False

    instruction = CONFIGURABLE_INSTRUCTIONS.get(instruction_key)
    if not instruction:
        return False

    content = filepath.read_text()
    pattern = instruction["pattern"]

    match = re.search(pattern, content)
    if not match:
        return False

    if dry_run:
        return True

    # Remove the matched text
    new_content = content[:match.start()] + content[match.end():]

    # Clean up: remove resulting double+ blank lines
    new_content = re.sub(r"\n{3,}", "\n\n", new_content)

    # Clean up: remove empty Session Discipline section if it only has the header left
    # Match "## Session Discipline\n" followed by only whitespace or another heading
    new_content = re.sub(
        r"## Session Discipline\n\s*(?=\n## |\n# |\Z)",
        "",
        new_content,
    )

    # Final cleanup of trailing whitespace
    new_content = new_content.rstrip() + "\n"

    filepath.write_text(new_content)
    return True


def add_instruction_to_file(
    filepath: Path, instruction_key: str, dry_run: bool = False
) -> bool:
    """Add a configurable instruction to a file if not already present.

    Appends the instruction under the appropriate section header.

    Args:
        filepath: Path to the file to modify.
        instruction_key: Key from CONFIGURABLE_INSTRUCTIONS.
        dry_run: If True, don't modify the file.

    Returns:
        True if the instruction was added (or would be added in dry_run).
    """
    if not filepath.exists():
        return False

    instruction = CONFIGURABLE_INSTRUCTIONS.get(instruction_key)
    if not instruction:
        return False

    content = filepath.read_text()

    # Check if already present
    if re.search(instruction["pattern"], content):
        return False

    if dry_run:
        return True

    text = instruction["text"]
    bullet = f"- {text}"

    # Try to find a "Session Discipline" section to append to
    section_match = re.search(r"(## Session Discipline\n)", content)
    if section_match:
        insert_pos = section_match.end()
        new_content = content[:insert_pos] + bullet + "\n" + content[insert_pos:]
    else:
        # Append a new section at the end
        new_content = content.rstrip() + "\n\n## Session Discipline\n" + bullet + "\n"

    filepath.write_text(new_content)
    return True


def get_all_agent_keys() -> List[str]:
    """Get all agent keys that have instruction files."""
    registry = load_agent_registry()
    return [
        key
        for key, agent in registry.get("agents", {}).items()
        if agent.get("instruction_file")
    ]


def get_agent_display_name(agent_key: str) -> str:
    """Get the display name for an agent."""
    registry = load_agent_registry()
    agent = registry.get("agents", {}).get(agent_key, {})
    return agent.get("display_name", agent_key)


def apply_instruction_config(
    instruction_key: str,
    agent_configs: Dict[str, bool],
    tracked_repos: List[Path],
    dry_run: bool = False,
) -> Dict[str, List[str]]:
    """Apply configurable instruction settings across all agent files.

    For each agent, either adds or removes the instruction from both
    the global file and all per-project files.

    Args:
        instruction_key: Key from CONFIGURABLE_INSTRUCTIONS.
        agent_configs: {agent_key: enabled} mapping.
        tracked_repos: List of tracked project directories.
        dry_run: If True, report changes without applying them.

    Returns:
        Dict with "added" and "removed" lists of affected file paths.
    """
    results: Dict[str, List[str]] = {"added": [], "removed": []}

    for agent_key, enabled in agent_configs.items():
        # Global file
        global_file = get_agent_global_file(agent_key)
        if global_file and global_file.exists():
            if enabled:
                if add_instruction_to_file(global_file, instruction_key, dry_run):
                    results["added"].append(str(global_file))
            else:
                if remove_instruction_from_file(global_file, instruction_key, dry_run):
                    results["removed"].append(str(global_file))

        # Per-project files
        for repo_path in tracked_repos:
            project_file = get_agent_project_file(agent_key, repo_path)
            if project_file and project_file.exists():
                if enabled:
                    if add_instruction_to_file(
                        project_file, instruction_key, dry_run
                    ):
                        results["added"].append(str(project_file))
                else:
                    if remove_instruction_from_file(
                        project_file, instruction_key, dry_run
                    ):
                        results["removed"].append(str(project_file))

    return results
