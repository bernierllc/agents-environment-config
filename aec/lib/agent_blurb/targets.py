"""Discover which agent instruction files exist on disk per scope.

Reuses existing AEC helpers (`get_agent_global_file`, `get_agent_project_file`,
`load_agent_registry`) so path-resolution logic lives in one place.
"""

import re
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
    scope: str, root: Optional[Path] = None, canonical: bool = True
) -> List[AgentTarget]:
    """Return all existing agent instruction files for ``scope``.

    Walks the agent registry in declared order and returns one
    :class:`AgentTarget` per agent whose instruction file exists on disk.
    Files that ``@``-import another target are dropped (see
    :func:`drop_importers`) unless ``canonical`` is False.

    Args:
        scope: ``"project"`` or ``"global"``.
        root: Required for ``project`` scope; ignored for ``global``.
        canonical: ``False`` keeps importer files, for resolving an explicit
            selection with :func:`canonicalize`.
    """
    registry = load_agent_registry()
    out: List[AgentTarget] = []
    for agent_key in registry.get("agents", {}).keys():
        path = _resolve_path(agent_key, scope=scope, root=root)
        if path is not None and path.exists():
            out.append(AgentTarget(agent_key=agent_key, path=path))
    return drop_importers(out) if canonical else out


# Claude Code ignores imports inside fenced code blocks and code spans. A fence
# closes on a line of at least the same length; an unclosed one runs to EOF.
_CODE_FENCE = re.compile(
    r"^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?(?:^ {0,3}\1[`~]*[ \t]*$|\Z)",
    re.MULTILINE | re.DOTALL,
)
# A span opens and closes with the same run of backticks (``@x`` is one span).
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)[^\n]*?(?<!`)\1(?!`)")
# An import is ``@path`` at the start of a word, anywhere in a line (not the
# ``@`` inside an email address).
_IMPORT_REF = re.compile(r"(?<!\S)@([^\s`]+)")
_TRAILING_PUNCT = ".,;:!?)\"'"
# Only these agents expand ``@file`` imports. Codex injects AGENTS.md as-is, so
# an ``@GEMINI.md`` mention there is prose, not an import.
_IMPORTING_AGENTS = frozenset({"claude", "gemini", "qwen"})


def _imported_paths(target: AgentTarget) -> set:
    """Resolved paths ``target`` imports with ``@file`` (empty if it can't import)."""
    if target.agent_key not in _IMPORTING_AGENTS:
        return set()
    path = target.path
    text = path.read_text(encoding="utf-8", errors="replace")
    text = _CODE_SPAN.sub("", _CODE_FENCE.sub("", text))
    out = set()
    for m in _IMPORT_REF.findall(text):
        try:
            out.add((path.parent / Path(m.rstrip(_TRAILING_PUNCT)).expanduser()).resolve())
        except (RuntimeError, ValueError, OSError):
            # Prose such as "@~nosuchuser" is not a resolvable import; skip it.
            continue
    return out


def drop_importers(targets: List[AgentTarget]) -> List[AgentTarget]:
    """Drop every target that ``@``-imports another target.

    The agent reads the imported file through the import, so a block written
    into both files is loaded twice. The imported file is the canonical one.
    """
    resolved = {t.path.resolve() for t in targets}
    return [
        t for t in targets
        if not (_imported_paths(t) & (resolved - {t.path.resolve()}))
    ]


def canonicalize(
    selected: List[AgentTarget], existing: List[AgentTarget]
) -> List[AgentTarget]:
    """Replace each selected importer with the existing target(s) it imports.

    An explicit selection of an importer (``CLAUDE.md`` importing
    ``AGENTS.md``) resolves to the imported file instead of vanishing; chains
    (A imports B imports C) resolve to the last file.
    Result is de-duplicated, in ``selected`` order.
    """
    by_path = {t.path.resolve(): t for t in existing}

    def leaves(t: AgentTarget, seen: frozenset) -> List[AgentTarget]:
        seen = seen | {t.path.resolve()}
        nxt = (_imported_paths(t) & set(by_path)) - seen
        if not nxt:
            return [t]
        return [leaf for p in sorted(nxt) for leaf in leaves(by_path[p], seen)]

    out: List[AgentTarget] = []
    for t in selected:
        for target in leaves(t, frozenset()):
            if target not in out:
                out.append(target)
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
