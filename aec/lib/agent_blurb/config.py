"""JSON source of truth for the agent blurb feature.

See docs/superpowers/specs/2026-05-12-aec-agent-blurb-design.md §5.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, TypedDict

from aec.lib.agent_blurb.profile import expand_profile
from aec.lib.atomic_write import atomic_write_text

SCHEMA_VERSION = 1
CONFIG_FILENAME = "agent-blurb.json"


class TargetRecord(TypedDict):
    agent_key: str  # e.g. "claude", "codex", "gemini" — resolves to file via registry
    path: str  # relative to scope root (project: repo root; global: $HOME)
    template_hash: str
    content_hash: str
    written_at: str  # ISO 8601 UTC


class AgentBlurbConfig(TypedDict):
    schema: int
    aec_version_last_write: str
    scope: str  # "project" | "global"
    profile: str  # "conservative" | "balanced" | "permissive" | "custom"
    matrix: Dict[str, Dict[str, str]]
    targets: List[TargetRecord]


def config_path(scope: str, root: Optional[Path] = None) -> Path:
    """Return the path to the agent-blurb.json for the given scope.

    For project scope, `root` must be supplied (the repo root).
    For global scope, `root` is ignored and the path is rooted at Path.home().
    """
    if scope == "project":
        if root is None:
            raise ValueError("project scope requires root")
        return root / ".aec" / CONFIG_FILENAME
    if scope == "global":
        return Path.home() / ".aec" / CONFIG_FILENAME
    raise ValueError(f"Unknown scope: {scope!r}")


def new_skeleton(
    scope: str,
    profile: str,
    aec_version: str,
    matrix_override: Optional[Dict[str, Dict[str, str]]] = None,
) -> AgentBlurbConfig:
    """Create a fresh config dict.

    If profile is one of the named profiles, the matrix is generated from
    PROFILES. If profile is "custom", `matrix_override` is merged onto the
    `balanced` matrix as a starting point.
    """
    if profile == "custom":
        matrix = expand_profile("balanced")
        if matrix_override:
            for it, settings in matrix_override.items():
                if it in matrix:
                    matrix[it].update(settings)
    else:
        matrix = expand_profile(profile)

    return {
        "schema": SCHEMA_VERSION,
        "aec_version_last_write": aec_version,
        "scope": scope,
        "profile": profile,
        "matrix": matrix,
        "targets": [],
    }


def load_config(scope: str, root: Optional[Path] = None) -> Optional[AgentBlurbConfig]:
    """Load the agent-blurb config for a scope, or return None if missing."""
    path = config_path(scope, root)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(
    data: AgentBlurbConfig, scope: str, root: Optional[Path] = None
) -> None:
    """Write the agent-blurb config atomically. Creates parent dirs."""
    path = config_path(scope, root)
    atomic_write_text(path, json.dumps(data, indent=2) + "\n")
