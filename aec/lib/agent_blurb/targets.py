"""Discover which agent instruction files exist on disk per scope.

Reuses existing AEC helpers (`get_agent_global_file`, `get_agent_project_file`,
`load_agent_registry`) so path-resolution logic lives in one place.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from aec.lib.configurable_instructions import (
    get_agent_global_file,
    get_agent_project_file,
)
from aec.lib.registry import load_agent_registry


@dataclass
class AgentTarget:
    """An existing agent instruction file paired with its registry key."""

    agent_key: str
    path: Path


def discover_targets(
    scope: str, root: Optional[Path] = None
) -> List[AgentTarget]:
    """Return all existing agent instruction files for ``scope``.

    Walks the agent registry in declared order and returns one
    :class:`AgentTarget` per agent whose instruction file exists on disk.

    Args:
        scope: ``"project"`` or ``"global"``.
        root: Required for ``project`` scope; ignored for ``global``.
    """
    registry = load_agent_registry()
    out: List[AgentTarget] = []
    for agent_key in registry.get("agents", {}).keys():
        path = _resolve_path(agent_key, scope=scope, root=root)
        if path is not None and path.exists():
            out.append(AgentTarget(agent_key=agent_key, path=path))
    return out


def resolve_path_for_agent_key(
    agent_key: str,
    scope: str,
    root: Optional[Path] = None,
) -> Path:
    """Return the canonical instruction-file path for ``agent_key`` in ``scope``.

    Raises:
        KeyError: if ``agent_key`` is not in the registry.
        ValueError: if ``scope`` is unknown, or ``project`` scope is
            requested without a ``root``, or the agent has no instruction
            file / global directory configured.
    """
    registry = load_agent_registry()
    if agent_key not in registry.get("agents", {}):
        raise KeyError(f"Unknown agent_key: {agent_key!r}")
    path = _resolve_path(agent_key, scope=scope, root=root)
    if path is None:
        raise ValueError(
            f"Agent {agent_key!r} has no instruction file for scope {scope!r}"
        )
    return path


def _resolve_path(
    agent_key: str, scope: str, root: Optional[Path]
) -> Optional[Path]:
    """Internal: resolve via the existing AEC helpers without raising on missing."""
    if scope == "project":
        if root is None:
            raise ValueError("project scope requires root")
        return get_agent_project_file(agent_key, root)
    if scope == "global":
        return get_agent_global_file(agent_key)
    raise ValueError(f"Unknown scope: {scope!r}")
