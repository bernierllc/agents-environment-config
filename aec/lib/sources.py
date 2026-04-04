"""Source management: discover available items, check staleness, fetch updates."""

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
        item_type: One of 'skills', 'rules', 'agents'

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
    return {}


def _discover_available_rules(source_dir: Path) -> dict:
    """Discover available rules from the agent-rules source."""
    rules = {}
    if not source_dir.exists():
        return rules
    for md_file in sorted(source_dir.rglob("*.md")):
        if md_file.name.startswith("."):
            continue
        rel = md_file.relative_to(source_dir)
        name = str(rel).removesuffix(".md")
        text = md_file.read_text(encoding="utf-8")
        fm = parse_yaml_frontmatter(text) or {}
        rules[name] = {
            "version": fm.get("version", "0.0.0"),
            "description": fm.get("description", ""),
            "path": str(rel),
        }
    return rules


def _discover_available_agents(source_dir: Path) -> dict:
    """Discover available agents from the agents source."""
    agents = {}
    if not source_dir.exists():
        return agents
    for md_file in sorted(source_dir.rglob("*.md")):
        if md_file.name.startswith("."):
            continue
        name = md_file.stem
        text = md_file.read_text(encoding="utf-8")
        fm = parse_yaml_frontmatter(text) or {}
        agents[name] = {
            "version": fm.get("version", "0.0.0"),
            "description": fm.get("description", ""),
            "path": md_file.name,
        }
    return agents


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
    }


def check_staleness(manifest: dict, max_age_hours: int = 24) -> bool:
    """Check if sources are stale."""
    return is_stale(manifest, max_age_hours)


def fetch_latest(repo_path: Optional[Path] = None) -> bool:
    """Pull latest AEC repo and update submodules. Returns True on success."""
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
            ["git", "submodule", "update", "--init", "--recursive"],
            cwd=repo_path, capture_output=True, check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False
