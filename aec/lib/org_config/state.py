"""Per-org state file IO.

State files live at ``<orgs_dir>/<org_id>.state.json`` and record what
was last applied for that org (config hash, trust mode, timestamps, etc.).

Two correctness requirements:

  1. **Atomic writes.** A half-written state file would leave the org in
     an indeterminate state. ``write_state`` writes to ``<state>.tmp.<pid>``
     and uses ``os.replace`` for the atomic rename.
  2. **Mutual exclusion.** Concurrent ``aec`` invocations may both try
     to update state. We hold an exclusive ``fcntl.flock`` on the
     ``<state>.lock`` companion file for the duration of the write.

Datetime fields are intentionally stored as ISO-8601 UTC strings rather
than serialized ``datetime`` objects — keeps the on-disk format stable
and editor-readable.
"""
from __future__ import annotations

import dataclasses
import fcntl
import json
import os
from dataclasses import dataclass
from typing import Optional

from .errors import OrgConfigError
from .paths import OrgPaths


@dataclass(frozen=True)
class OrgState:
    org_id: str
    config_version: str
    config_hash: str
    trust_mode: str
    pubkey_fingerprint: Optional[str]
    pubkey_source: Optional[str]
    last_verified_at: str
    last_applied_at: str
    source_of_record: str
    unsigned_warning_acknowledged_at: Optional[str]
    key_rotation_pending: Optional[dict]
    # URL the config was fetched from, when source_of_record is "url".
    source_url: Optional[str] = None


class OrgStateCorruptError(OrgConfigError):
    """State file exists but its JSON is unreadable."""


def read_state(paths: OrgPaths, org_id: str) -> Optional[OrgState]:
    state_path = paths.state_for(org_id)
    if not state_path.exists():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OrgStateCorruptError(
            f"corrupt state file at {state_path}: {exc}"
        ) from exc
    return OrgState(**data)


def write_state(paths: OrgPaths, state: OrgState) -> None:
    state_path = paths.state_for(state.org_id)
    lock_path = paths.state_lock_for(state.org_id)
    tmp_path = state_path.with_name(f"{state_path.name}.tmp.{os.getpid()}")

    state_path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(dataclasses.asdict(state), indent=2, sort_keys=True)

    with open(lock_path, "w") as lock_fp:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
        try:
            tmp_path.write_text(payload, encoding="utf-8")
            os.replace(tmp_path, state_path)
        finally:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
