"""Persisted conflict resolutions with input-hash invalidation.

A resolution records the user's decision for one conflict, keyed by the
``conflict_id`` and stamped with an ``input_hash`` derived from the exact
config hashes of the participating orgs (principle P3). If any contributing
config changes, the input hash no longer matches and the resolution is stale —
AEC re-prompts rather than honoring a decision made against different inputs.

Storage:
  * ``~/.aec/conflict-resolutions.json``         — live resolutions
  * ``~/.aec/conflict-resolutions.history.json`` — superseded/invalidated ones

Writes are atomic (tmp + ``os.replace``) and serialized with an ``flock`` on a
companion lock file, mirroring :mod:`aec.lib.org_config.state`.
"""
from __future__ import annotations

import dataclasses
import fcntl
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Iterable, Optional

from .errors import OrgConfigError
from .paths import OrgPaths

SCHEMA_VERSION = "1.0"
_HISTORY_LIMIT = 100


@dataclass(frozen=True)
class Resolution:
    conflict_id: str
    decision: str
    input_hash: str
    decided_at: str
    decided_by: Optional[str] = None
    notes: Optional[str] = None


class ResolutionsCorruptError(OrgConfigError):
    """Resolutions file exists but its JSON is unreadable."""


def input_hash_for(org_ids: Iterable[str], org_hashes: dict[str, str]) -> str:
    """Hash the contributing orgs' config hashes into one invalidation key."""
    parts = sorted(f"{oid}:{org_hashes.get(oid, '')}" for oid in org_ids)
    return "sha256:" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def is_valid(resolution: Resolution, current_input_hash: str) -> bool:
    return resolution.input_hash == current_input_hash


def _read_file(path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResolutionsCorruptError(f"corrupt resolutions file at {path}: {exc}") from exc
    return data.get("resolutions", [])


def load_resolutions(paths: OrgPaths) -> dict[str, Resolution]:
    out: dict[str, Resolution] = {}
    for raw in _read_file(paths.conflict_resolutions):
        out[raw["conflict_id"]] = Resolution(
            conflict_id=raw["conflict_id"],
            decision=raw["decision"],
            input_hash=raw["input_hash"],
            decided_at=raw["decided_at"],
            decided_by=raw.get("decided_by"),
            notes=raw.get("notes"),
        )
    return out


def load_history(paths: OrgPaths) -> list[dict]:
    return _read_file(paths.conflict_resolutions_history)


def _atomic_write(path, payload: dict, lock_path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    text = json.dumps(payload, indent=2, sort_keys=True)
    with open(lock_path, "w") as lock_fp:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
        try:
            tmp_path.write_text(text, encoding="utf-8")
            os.replace(tmp_path, path)
        finally:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)


def _lock_for(path):
    return path.with_name(path.name + ".lock")


def save_resolution(paths: OrgPaths, resolution: Resolution, *, reason: str = "superseded") -> None:
    """Persist ``resolution``, moving any prior decision for the same conflict
    (with a different input hash/decision) into the history file."""
    current = load_resolutions(paths)
    prior = current.get(resolution.conflict_id)
    if prior is not None and prior != resolution:
        _append_history(paths, prior, reason=reason)

    current[resolution.conflict_id] = resolution
    payload = {
        "schema_version": SCHEMA_VERSION,
        "resolutions": [dataclasses.asdict(r) for r in current.values()],
    }
    _atomic_write(paths.conflict_resolutions, payload, _lock_for(paths.conflict_resolutions))


def prune_invalid(paths: OrgPaths, valid_input_hashes: dict[str, str]) -> list[str]:
    """Drop resolutions whose conflict is gone or whose input hash changed.

    ``valid_input_hashes`` maps the currently-open conflict_ids to their current
    input hash. Returns the conflict_ids that were pruned.
    """
    current = load_resolutions(paths)
    pruned: list[str] = []
    keep: dict[str, Resolution] = {}
    for cid, res in current.items():
        if valid_input_hashes.get(cid) == res.input_hash:
            keep[cid] = res
        else:
            pruned.append(cid)
            _append_history(paths, res, reason="invalidated")

    if pruned:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "resolutions": [dataclasses.asdict(r) for r in keep.values()],
        }
        _atomic_write(paths.conflict_resolutions, payload, _lock_for(paths.conflict_resolutions))
    return pruned


def _append_history(paths: OrgPaths, resolution: Resolution, *, reason: str) -> None:
    from datetime import datetime, timezone

    history = load_history(paths)
    entry = dataclasses.asdict(resolution)
    entry["invalidated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    entry["reason"] = reason
    history.append(entry)
    history = history[-_HISTORY_LIMIT:]
    payload = {"schema_version": SCHEMA_VERSION, "resolutions": history}
    _atomic_write(
        paths.conflict_resolutions_history,
        payload,
        _lock_for(paths.conflict_resolutions_history),
    )
