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


class PendingChangeset:
    def __init__(self, paths: Iterable[Path], short: str, long: str, kind: str) -> None:
        self.short, self.long, self.kind = short, long, kind
        self.reverses: Optional[str] = None
        self._before: Dict[Path, Optional[bytes]] = {}
        for p in paths:
            p = Path(p).absolute()
            self._before[p] = _read(p)

    def discard(self) -> None:
        self._before = {}

    def commit(self) -> Optional[Changeset]:
        changes: List[FileChange] = []
        blobs: Dict[str, bytes] = {}
        for path, before in self._before.items():
            after = _read(path)
            b = None if before is None else _sha(before)
            a = None if after is None else _sha(after)
            if a == b:
                continue
            if before is not None:
                blobs[b] = before
            if after is not None:
                blobs[a] = after
            changes.append(FileChange(path, b, a))
        if not changes:
            return None

        now = datetime.now(timezone.utc)
        root = rollbacks_dir()
        while True:
            cs_id = now.strftime("%Y%m%dT%H%M%SZ-") + secrets.token_hex(2)
            if not (root / cs_id).exists():
                break
        cs = Changeset(
            id=cs_id,
            created_at=now.isoformat(timespec="microseconds"),  # fixed width, so it sorts as a string
            kind=self.kind,
            short=self.short,
            long=self.long,
            files=changes,
            reverses=self.reverses,
        )
        (cs.dir / "blobs").mkdir(parents=True)
        for sha, data in blobs.items():
            _write_bytes_atomic(cs.dir / "blobs" / sha, data)
        atomic_write_json(cs.dir / _MANIFEST, _to_json(cs))
        self._before = {}
        return cs


def begin(paths: Iterable[Path], short: str, long: str, kind: str) -> PendingChangeset:
    return PendingChangeset(paths, short, long, kind)


def load(cs_id: str) -> Changeset:
    manifest = rollbacks_dir() / cs_id / _MANIFEST
    try:
        return _from_json(json.loads(manifest.read_text(encoding="utf-8")))
    except FileNotFoundError:
        raise ChangesetNotFound(cs_id) from None


def list_changesets() -> List[Changeset]:
    root = rollbacks_dir()
    if not root.is_dir():
        return []
    out: List[Changeset] = []
    for d in sorted(root.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        try:
            out.append(load(d.name))
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

    pending = begin(
        [fc.path for fc in orig.files],
        short=f"Revert: {orig.short}",
        long=f"Reverts changeset {orig.id} ({orig.short}).",
        kind="revert",
    )
    pending.reverses = orig.id
    # Load every blob before touching any file, so a missing blob can't leave a half-restore.
    restore = [(fc.path, None if fc.before is None else _blob(orig, fc.before)) for fc in orig.files]
    for path, data in restore:
        if data is None:
            path.unlink(missing_ok=True)
        else:
            _write_bytes_atomic(path, data)
    new = pending.commit()
    if new is None:
        raise NothingToRevert(f"reverting {orig.id} would change no file")
    orig.reversed_by = new.id
    atomic_write_json(orig.dir / _MANIFEST, _to_json(orig))
    return new
