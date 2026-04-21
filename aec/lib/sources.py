"""Source management: discover items, check staleness, fetch updates."""

import json
import subprocess
from pathlib import Path
from typing import Optional

from .config import get_repo_root
from .manifest_v2 import is_stale
from .skills_manifest import discover_available_skills, parse_yaml_frontmatter


def discover_available(source_dir: Path, item_type: str) -> dict:
    """Discover available items of a given type from the source directory.

    Args:
        source_dir: Root of the source (e.g., repo/.claude/skills/)
        item_type: One of 'skills', 'rules', 'agents', 'mcps'

    Returns:
        Dict of name -> {version, description, path, ...}
    """
    if not source_dir.exists():
        return {}
    if item_type == "skills":
        return discover_available_skills(source_dir)
    elif item_type == "rules":
        return _discover_available_rules(source_dir)
    elif item_type == "agents":
        return _discover_available_agents(source_dir)
    elif item_type == "mcps":
        return _discover_available_mcps(source_dir)
    return {}


def _discover_available_rules(source_dir: Path) -> dict:
    """Discover available rules from the agent-rules source.

    Only includes files with valid frontmatter containing name and version.
    """
    rules = {}
    if not source_dir.exists():
        return rules
    for md_file in sorted(source_dir.rglob("*.md")):
        if md_file.name.startswith("."):
            continue
        text = md_file.read_text(encoding="utf-8")
        fm = parse_yaml_frontmatter(text)
        if not fm or "name" not in fm or "version" not in fm:
            continue
        rel = md_file.relative_to(source_dir)
        name = fm["name"]
        rules[name] = {
            "version": fm["version"],
            "description": fm.get("description", ""),
            "path": str(rel),
        }
    return rules


def _discover_available_agents(source_dir: Path) -> dict:
    """Discover available agents from the agents source.

    Only includes files with valid frontmatter containing name and version.
    Files without proper frontmatter (README, CONTRIBUTING, etc.) are skipped.
    """
    agents = {}
    if not source_dir.exists():
        return agents
    for md_file in sorted(source_dir.rglob("*.md")):
        if md_file.name.startswith("."):
            continue
        text = md_file.read_text(encoding="utf-8")
        fm = parse_yaml_frontmatter(text)
        if not fm or "name" not in fm or "version" not in fm:
            continue
        name = md_file.stem
        rel = md_file.relative_to(source_dir)
        agents[name] = {
            "version": fm["version"],
            "description": fm.get("description", ""),
            "author": fm.get("author", ""),
            "division": fm.get("division", ""),
            "path": str(rel),
        }
    return agents


def _discover_available_mcps(source_dir: Path) -> dict:
    """Discover available MCP servers from the mcp-servers source directory.

    Each MCP server is a subdirectory containing an mcp.json file with at
    minimum 'name' and 'version' fields.
    """
    mcps = {}
    if not source_dir.exists():
        return mcps
    for mcp_dir in sorted(source_dir.iterdir()):
        if not mcp_dir.is_dir() or mcp_dir.name.startswith("."):
            continue
        mcp_file = mcp_dir / "mcp.json"
        if not mcp_file.exists():
            continue
        try:
            data = json.loads(mcp_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if "name" not in data or "version" not in data:
            continue
        name = data["name"]
        mcps[name] = {
            "version": data["version"],
            "description": data.get("description", ""),
            "path": mcp_dir.name,
        }
    return mcps


def get_source_dirs() -> dict:
    """Get source directories for each item type from the AEC repo.

    These are the AEC repo's source directories (where available items
    are defined), NOT the user's install targets.

    Returns dict of item_type -> Path.
    """
    repo = get_repo_root()
    if repo is None:
        return {}
    return {
        "skills": repo / ".claude" / "skills",
        "rules": repo / ".agent-rules",
        "agents": repo / ".claude" / "agents",
        "mcps": repo / "mcp-servers",
    }


def check_staleness(manifest: dict, max_age_hours: int = 24) -> bool:
    """Check if sources are stale."""
    return is_stale(manifest, max_age_hours)


def fetch_latest(repo_path: Optional[Path] = None) -> bool:
    """Pull latest AEC repo and update submodules to remote branch tips.

    Uses ``git submodule update --remote`` so skills/agents track the latest
    commits on their default branches (same as the post-merge hook), not only
    the superproject's recorded gitlinks.
    """
    if repo_path is None:
        repo_path = get_repo_root()
    if repo_path is None:
        return False
    try:
        subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=repo_path, capture_output=True, check=True,
        )
        subprocess.run(
            [
                "git",
                "submodule",
                "update",
                "--init",
                "--recursive",
                "--remote",
            ],
            cwd=repo_path, capture_output=True, check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False
