"""Changeset store: snapshot files before AEC changes them so any change can be
rolled back byte-exact. A rollback is itself a changeset, so undo-the-undo is a
redo.

Layout: ``rollbacks/<id>/rollback.json`` plus ``rollbacks/<id>/blobs/<sha256>``
(content-addressed raw bytes). Pure pathlib/hashlib/os, so it behaves the same
on Windows, macOS and Linux.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import os
import secrets
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from aec.lib.atomic_write import atomic_write_json
from aec.lib.config import AEC_HOME

logger = logging.getLogger(__name__)

SCHEMA = 1
_MANIFEST = "rollback.json"
_PENDING = "pending.json"  # journal of a change in progress


class ChangesetError(Exception):
    """Base class for changeset errors."""


class ChangesetNotFound(ChangesetError, KeyError):
    """No changeset with that id."""


class AlreadyReverted(ChangesetError):
    """The changeset already has a reverting changeset."""


class NothingToRevert(ChangesetError):
    """Reverting would change no file."""


class ConflictError(ChangesetError):
    """Files were edited after the change; carries the conflicting files."""

    def __init__(self, conflicts: "List[FileChange]") -> None:
        self.conflicts = conflicts
        super().__init__(
            "files changed since this changeset: "
            + ", ".join(str(fc.path) for fc in conflicts)
        )


@dataclass
class FileChange:
    path: Path
    before: Optional[str]  # sha256, None = file did not exist
    after: Optional[str]  # sha256, None = file deleted


@dataclass
class Changeset:
    id: str
    created_at: str
    kind: str
    short: str
    long: str
    files: List[FileChange] = field(default_factory=list)
    reverses: Optional[str] = None
    reversed_by: Optional[str] = None

    @property
    def dir(self) -> Path:
        return rollbacks_dir() / self.id


def rollbacks_dir() -> Path:
    return AEC_HOME / "rollbacks"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(path: Path) -> Optional[bytes]:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None  # missing file is a recorded state (before/after = None)


def _current_hash(path: Path) -> Optional[str]:
    data = _read(path)
    return None if data is None else _sha(data)


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        if path.exists():
            os.chmod(tmp, path.stat().st_mode & 0o7777)  # mkstemp creates 0600
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _to_json(cs: Changeset) -> dict:
    return {
        "schema": SCHEMA,
        "id": cs.id,
        "created_at": cs.created_at,
        "kind": cs.kind,
        "short": cs.short,
        "long": cs.long,
        "reverses": cs.reverses,
        "reversed_by": cs.reversed_by,
        "files": [
            {"path": str(fc.path), "before": fc.before, "after": fc.after}
            for fc in cs.files
        ],
    }


def _from_json(d: dict) -> Changeset:
    return Changeset(
        id=d["id"],
        created_at=d["created_at"],
        kind=d["kind"],
        short=d["short"],
        long=d["long"],
        reverses=d.get("reverses"),
        reversed_by=d.get("reversed_by"),
        files=[
            FileChange(Path(f["path"]), f.get("before"), f.get("after"))
            for f in d["files"]
        ],
    )


def _new_id(root: Path, now: datetime) -> str:
    while True:
        cs_id = now.strftime("%Y%m%dT%H%M%SZ-") + secrets.token_hex(2)
        if not (root / cs_id).exists():
            return cs_id


def _from_journal(journal: dict) -> Changeset:
    """The changeset a journal describes, using each file's current state (no writes)."""
    changes: List[FileChange] = []
    for path_str, b in journal["before"].items():
        path = Path(path_str)
        a = _current_hash(path)
        if a != b:
            changes.append(FileChange(path, b, a))
    return Changeset(
        id=journal["id"],
        created_at=journal["created_at"],
        kind=journal["kind"],
        short=journal["short"],
        long=journal["long"],
        files=changes,
        reverses=journal.get("reverses"),
    )


def _finalize(d: Path, journal: dict) -> Optional[Changeset]:
    """Record a journal's change: after-blobs plus manifest. None if nothing changed."""
    if not (d / _PENDING).exists():
        # Someone rolled this change back while it was running; never touch that history.
        raise ChangesetError(f"change {journal['id']} was rolled back while running; not recorded")
    changes: List[FileChange] = []
    for path_str, b in journal["before"].items():
        path = Path(path_str)
        data = _read(path)  # one read, so the recorded hash always matches the stored blob
        a = None if data is None else _sha(data)
        if a == b:
            continue
        if data is not None:
            _write_bytes_atomic(d / "blobs" / a, data)
        changes.append(FileChange(path, b, a))
    if not changes:
        shutil.rmtree(d)
        return None
    cs = _from_journal(journal)
    cs.files = changes
    atomic_write_json(d / _MANIFEST, _to_json(cs))
    (d / _PENDING).unlink()
    return cs


class PendingChangeset:
    """Snapshots files to disk before the caller changes them.

    The before-bytes and a journal are written when this is created, so if the
    store cannot be written nothing has been touched yet, and an interrupted
    change can still be finalized later (see list_changesets).
    """

    def __init__(
        self, paths: Iterable[Path], short: str, long: str, kind: str, reverses: Optional[str] = None
    ) -> None:
        paths = [Path(p).absolute() for p in paths]
        links = [str(p) for p in paths if p.is_symlink()]
        if links:
            # A restore writes a regular file, so it could not put a link back.
            raise ChangesetError("AEC does not change symlinked files: " + ", ".join(links))
        now = datetime.now(timezone.utc)
        root = rollbacks_dir()
        self.id = _new_id(root, now)
        self._dir = root / self.id
        (self._dir / "blobs").mkdir(parents=True)
        before: Dict[str, Optional[str]] = {}
        for p in paths:
            data = _read(p)
            before[str(p)] = None if data is None else _sha(data)
            if data is not None:
                _write_bytes_atomic(self._dir / "blobs" / before[str(p)], data)
        self._journal = {
            "schema": SCHEMA,
            "id": self.id,
            "created_at": now.isoformat(timespec="microseconds"),  # fixed width, so it sorts as a string
            "kind": kind,
            "short": short,
            "long": long,
            "reverses": reverses,
            "before": before,
        }
        atomic_write_json(self._dir / _PENDING, self._journal)

    def commit(self) -> Optional[Changeset]:
        """Record every snapshotted file's current state; None if nothing changed."""
        return _finalize(self._dir, self._journal)


def begin(
    paths: Iterable[Path], short: str, long: str, kind: str, reverses: Optional[str] = None
) -> PendingChangeset:
    return PendingChangeset(paths, short, long, kind, reverses)


def load(cs_id: str) -> Changeset:
    """Load a changeset. One whose process never committed (crash, or still
    running) is read from its journal and the files' current state; loading
    never writes, so a running change is never finalized from under it."""
    d = rollbacks_dir() / cs_id
    try:
        return _from_json(json.loads((d / _MANIFEST).read_text(encoding="utf-8")))
    except FileNotFoundError:
        pass
    try:
        cs = _from_journal(json.loads((d / _PENDING).read_text(encoding="utf-8")))
    except FileNotFoundError:
        raise ChangesetNotFound(cs_id) from None
    cs.short += " (interrupted)"
    return cs


def list_changesets() -> List[Changeset]:
    root = rollbacks_dir()
    if not root.is_dir():
        return []
    out: List[Changeset] = []
    for d in sorted(root.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        try:
            cs = load(d.name)
            if cs.files:  # an interrupted change that touched nothing is noise
                out.append(cs)
        except (ChangesetNotFound, OSError, ValueError, KeyError, TypeError) as e:
            logger.warning("skipping unreadable changeset %s: %s", d.name, e)
    out.sort(key=lambda c: (c.created_at, c.id), reverse=True)  # id suffix is random within a second
    return out


def _blob(cs: Changeset, sha: str) -> bytes:
    try:
        return (cs.dir / "blobs" / sha).read_bytes()
    except FileNotFoundError:
        raise ChangesetError(f"changeset {cs.id} is missing blob {sha}") from None


def conflicts(cs: Changeset) -> List[FileChange]:
    return [fc for fc in cs.files if _current_hash(fc.path) != fc.after]


def diff_text(cs: Changeset, fc: FileChange) -> str:
    """Unified diff from the recorded after-state to the current file (display only)."""
    recorded = b"" if fc.after is None else _blob(cs, fc.after)
    current = _read(fc.path) or b""
    return "".join(
        difflib.unified_diff(
            recorded.decode("utf-8", errors="replace").splitlines(keepends=True),
            current.decode("utf-8", errors="replace").splitlines(keepends=True),
            fromfile=f"recorded {fc.path}",
            tofile=f"current {fc.path}",
        )
    )


def revert(cs_id: str, force: bool = False) -> Changeset:
    orig = load(cs_id)
    if orig.reversed_by:
        raise AlreadyReverted(f"{orig.id} was already reverted by {orig.reversed_by}")
    found = conflicts(orig)
    if found and not force:
        raise ConflictError(found)

    # Load every blob before touching any file, so a missing blob can't leave a half-restore.
    restore = [(fc.path, None if fc.before is None else _blob(orig, fc.before)) for fc in orig.files]
    pending = begin(
        [fc.path for fc in orig.files],
        short=f"Revert: {orig.short}",
        long=f"Reverts changeset {orig.id} ({orig.short}).",
        kind="revert",
        reverses=orig.id,
    )
    try:
        for path, data in restore:
            if data is None:
                path.unlink(missing_ok=True)
            else:
                _write_bytes_atomic(path, data)
    finally:
        # Record even a partial restore, so edits it overwrote can be brought back.
        new = pending.commit()
    if new is None:
        raise NothingToRevert(f"reverting {orig.id} would change no file")
    orig.reversed_by = new.id
    atomic_write_json(orig.dir / _MANIFEST, _to_json(orig))
    # An interrupted original is now settled; a late commit from its process fails loudly.
    (orig.dir / _PENDING).unlink(missing_ok=True)
    return new
