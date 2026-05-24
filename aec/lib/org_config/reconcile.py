"""Orchestrates conflict detection against persisted resolutions.

Ties together discovery (configs + their content hashes), pure conflict
detection, and the resolutions store: computes each conflict's current input
hash, auto-prunes resolutions invalidated by config changes, and reports which
conflicts remain open (unresolved or deferred).

Shared by ``aec org resolve``, ``aec doctor``, and the Phase 2e apply gate.
"""
from __future__ import annotations

from dataclasses import dataclass

from .conflicts import Conflict, detect_conflicts
from .discovery import discover_enrolled_orgs
from .paths import OrgPaths
from .resolutions import input_hash_for, is_valid, load_resolutions, prune_invalid


@dataclass(frozen=True)
class OpenConflict:
    conflict: Conflict
    input_hash: str


def scan_conflicts(paths: OrgPaths) -> tuple[list[Conflict], dict[str, str]]:
    """Return all detected conflicts and ``{conflict_id: input_hash}``."""
    orgs = discover_enrolled_orgs(paths)
    configs = [e.config for e in orgs]
    org_hashes = {e.config.org_id: e.content_hash for e in orgs}
    conflicts = detect_conflicts(configs)
    input_hashes = {
        c.conflict_id: input_hash_for((p.org_id for p in c.participants), org_hashes)
        for c in conflicts
    }
    return conflicts, input_hashes


def open_conflicts(paths: OrgPaths) -> list[OpenConflict]:
    """Conflicts that still need a decision, after auto-pruning stale ones."""
    conflicts, input_hashes = scan_conflicts(paths)
    prune_invalid(paths, input_hashes)
    resolutions = load_resolutions(paths)

    out: list[OpenConflict] = []
    for conflict in conflicts:
        ih = input_hashes[conflict.conflict_id]
        res = resolutions.get(conflict.conflict_id)
        if res is not None and is_valid(res, ih) and res.decision != "defer":
            continue
        out.append(OpenConflict(conflict=conflict, input_hash=ih))
    return out
