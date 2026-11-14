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
import itertools
import json
import os
from contextlib import contextmanager
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
    # None until an apply succeeds ("never applied").
    last_applied_at: Optional[str]
    source_of_record: str  # "local" | "url" | "git"
    unsigned_warning_acknowledged_at: Optional[str]
    key_rotation_pending: Optional[dict]
    # URL the config was fetched from, when source_of_record is "url".
    source_url: Optional[str] = None
    # git+<source_repo>#<source_ref>:<source_path>, when source_of_record is "git".
    source_repo: Optional[str] = None
    source_ref: Optional[str] = None
    source_path: Optional[str] = None
    resolved_commit: Optional[str] = None
    # Domain recorded at the last interactive enroll (dns_anchor). Part of the
    # trust anchor: a refresh compares fetched content against it, never the YAML.
    trust_dns_domain: Optional[str] = None
    # Something needs a human: {"kind": "review"|"verify_failed"|"trust_change"|"apply_failed", ...}.
    pending: Optional[dict] = None
    # {custom_source_id: commit} last approved and applied, so a source pinned
    # only by ref stays put until a refresh's review approves where it moved.
    source_commits: Optional[dict] = None


class OrgStateCorruptError(OrgConfigError):
    """State file exists but its JSON is unreadable."""


def read_state(paths: OrgPaths, org_id: str) -> Optional[OrgState]:
    recover_interrupted(paths)
    state_path = paths.state_for(org_id)
    if not state_path.exists():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OrgStateCorruptError(
            f"corrupt state file at {state_path}: {exc}"
        ) from exc
    # Ignore keys a newer AEC wrote, so an older AEC can still read the file.
    known = {f.name for f in dataclasses.fields(OrgState)}
    return OrgState(**{k: v for k, v in data.items() if k in known})


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


# --- All-or-nothing changes to org files ----------------------------------
#
# A snapshot hard-links an org's state file (and, if asked, its config YAML) to
# ``<file>.aec-prev.<pid>.<seq>`` before a change. Every writer replaces these
# files by rename (``write_state``, ``atomic_write_text``), never in place, so the
# link keeps the old content. Rolling back is a rename back: it writes no
# payload, so it works on a full disk too. A snapshot left behind by a process
# that died, or by a rollback that failed, is restored by the next reader.

_PREV = ".aec-prev."
_seq = itertools.count()
_open_links: set = set()  # prev paths of snapshots open in this process


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # alive, owned by another user
    return True


def _put_back(prev, live) -> None:
    # rename() is a no-op when both names already link the same file, which
    # would leave the snapshot behind: the file never changed, so just drop it.
    if live.exists() and os.path.samefile(prev, live):
        prev.unlink()
    else:
        os.replace(prev, live)


def recover_interrupted(paths: OrgPaths) -> None:
    """Roll back snapshots nobody will commit or restore: their process died, or
    their rollback failed. Each file goes back to its oldest such snapshot."""
    d = paths.orgs_dir
    if not d.exists():
        return
    by_live: dict = {}
    for prev in d.glob(f"*{_PREV}*"):
        name, _, tag = prev.name.rpartition(_PREV)
        pid, _, seq = tag.partition(".")
        if not (pid.isdigit() and seq.isdigit()) or prev in _open_links:
            continue
        if int(pid) != os.getpid() and _pid_alive(int(pid)):
            continue
        by_live.setdefault(d / name, []).append((int(seq), prev))
    errors = []
    for live, prevs in sorted(by_live.items()):
        prevs.sort()
        try:
            _put_back(prevs[0][1], live)
            for _, extra in prevs[1:]:
                extra.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(f"{live.name}: {exc}")
    if errors:
        raise OrgConfigError("could not roll back an interrupted org change: " + "; ".join(errors))


class StateSnapshot:
    """The given orgs' files as they were when the snapshot was taken.

    Call exactly one of ``restore()`` or ``drop()``. Until then a crash leaves
    the snapshot on disk, and the next ``read_state`` rolls the change back.
    """

    def __init__(self, paths: OrgPaths, org_ids, *, config: bool = False):
        recover_interrupted(paths)
        self.links: list = []  # (live, prev)
        seq = next(_seq)
        try:
            for org_id in org_ids:
                files = [paths.state_for(org_id)] + ([paths.config_for(org_id)] if config else [])
                for live in files:
                    if not live.exists():
                        continue
                    prev = live.with_name(f"{live.name}{_PREV}{os.getpid()}.{seq}")
                    os.link(live, prev)
                    _open_links.add(prev)
                    self.links.append((live, prev))
        except OSError:
            self.drop()
            raise

    def restore(self) -> None:
        """Put every file back. Tries them all; one it cannot put back keeps its
        snapshot, which ``recover_interrupted`` restores later."""
        errors = []
        for live, prev in self.links:
            _open_links.discard(prev)
            try:
                _put_back(prev, live)
            except OSError as exc:
                errors.append(f"{live.name}: {exc}")
        self.links = []
        if errors:
            raise OrgConfigError("could not roll back org state: " + "; ".join(errors))

    def drop(self) -> None:
        for _, prev in self.links:
            _open_links.discard(prev)
            prev.unlink(missing_ok=True)
        self.links = []


@contextmanager
def all_or_nothing(paths: OrgPaths, org_ids, *, config: bool = False):
    """Restore the orgs' files if the block raises; keep the changes otherwise."""
    snap = StateSnapshot(paths, org_ids, config=config)
    try:
        yield snap
    except BaseException:
        snap.restore()
        raise
    snap.drop()
