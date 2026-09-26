"""Ownership record for symlinks AEC creates -- keyed by link path.

Backs ``aec.lib.filesystem.is_our_symlink()``: whether AEC owns a symlink is
a lookup in this record, written by ``create_symlink()`` at creation time,
not a heuristic on the link's target. A checkout cloned under a
non-standard name, or moved/recloned after linking, is still recognised as
ours.

Pre-existing links from before this record existed are adopted by
``_legacy_store()``, which matches the retired substring heuristic against
the fixed set of locations AEC has ever created symlinks at (never an
arbitrary path). Until the record file exists, reads use that adopted view
in memory -- lookups never write, so dry runs and read-only state dirs are
safe. The first real write (``create_symlink()`` or a non-dry-run
``agent-tools setup`` via ``persist_legacy_migration()``) persists it, after which
the heuristic is never consulted again.

See docs/superpowers/plans/2026-09-25-managed-symlink-ownership.md.
"""

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

from .atomic_write import atomic_write_json
from .config import AEC_HOME

MANAGED_SYMLINKS_PATH = AEC_HOME / "managed-symlinks.json"
SCHEMA_VERSION = 1

# Substrings the retired heuristic matched against a link's raw target.
# Consulted only by _legacy_store(), and only for the fixed
# set of locations in _legacy_candidate_paths() -- never for an arbitrary
# path passed to is_our_symlink().
_LEGACY_SUBSTRINGS = ("agents-environment-config", ".agent-tools")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_store() -> dict:
    return {"schemaVersion": SCHEMA_VERSION, "links": {}}


def _load() -> dict:
    if not MANAGED_SYMLINKS_PATH.exists():
        return _legacy_store()
    try:
        data = json.loads(MANAGED_SYMLINKS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_store()
    if not isinstance(data, dict) or not isinstance(data.get("links"), dict):
        return _empty_store()
    return data


def _save(data: dict) -> None:
    atomic_write_json(MANAGED_SYMLINKS_PATH, data)


@contextmanager
def _locked() -> Iterator[None]:
    """Serialise read-modify-write of the record across AEC processes."""
    # ponytail: no lock on Windows (no fcntl); use msvcrt.locking if
    # concurrent installs there ever matter.
    if fcntl is None:
        yield
        return
    MANAGED_SYMLINKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_path = MANAGED_SYMLINKS_PATH.with_name(MANAGED_SYMLINKS_PATH.name + ".lock")
    with open(lock_path, "w") as lock_fp:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)


def _key(link_path: Path) -> str:
    """Normalise a link path to the record's key.

    Absolute and expanded, but NOT resolved -- resolving would follow the
    symlink (or fail to fully resolve a dangling one) instead of
    identifying the link itself.
    """
    return str(Path(link_path).expanduser().absolute())


def record_symlink(link_path: Path, source_path: Path) -> None:
    """Record that AEC created/owns the symlink at ``link_path -> source_path``."""
    with _locked():
        data = _load()  # first write persists the adopted legacy links too
        data["links"][_key(link_path)] = {
            "source": str(Path(source_path).expanduser().absolute()),
            "recordedAt": _now_iso(),
        }
        _save(data)


def forget_symlink(link_path: Path) -> None:
    """Drop ``link_path`` from the record. No-op if it isn't recorded."""
    with _locked():
        data = _load()
        if data["links"].pop(_key(link_path), None) is not None:
            _save(data)


def persist_legacy_migration() -> None:
    """Write the adopted legacy links if the record doesn't exist yet.

    Called by non-dry-run setup so the heuristic stops being consulted even
    when no new link needs creating. Raises OSError if the store is unwritable.
    """
    with _locked():
        if not MANAGED_SYMLINKS_PATH.exists():
            _save(_legacy_store())


def is_recorded(link_path: Path) -> bool:
    """True iff ``link_path`` is in the ownership record."""
    return recorded_source(link_path) is not None


def recorded_source(link_path: Path) -> Optional[str]:
    """The source AEC recorded for ``link_path``, or None if not recorded."""
    entry = _load()["links"].get(_key(link_path))
    return entry.get("source") if isinstance(entry, dict) else None


def normalize_target(link_path: Path, target: str) -> str:
    """Absolute form of a link target (relative targets resolve against the link's dir)."""
    return os.path.normpath(os.path.join(os.path.dirname(_key(link_path)), target))


def _legacy_candidate_paths() -> List[Path]:
    """Locations AEC has historically created managed symlinks at.

    Used only by _legacy_store() below. New links never need this
    list: create_symlink() records them directly at creation time.
    """
    # Deferred import: aec.lib re-exports these from aec.lib.config, and
    # tests monkeypatch the re-export (aec.lib.CLAUDE_DIR etc), not the
    # underlying config module -- so this must be looked up at call time.
    from . import AGENT_TOOLS_DIR, CLAUDE_DIR, CURSOR_DIR

    name = "agents-environment-config"
    return [
        AGENT_TOOLS_DIR / "rules" / name,
        AGENT_TOOLS_DIR / "agents" / name,
        AGENT_TOOLS_DIR / "commands" / name,
        AGENT_TOOLS_DIR / "skills" / name,
        CLAUDE_DIR / "agents" / name,
        CLAUDE_DIR / "skills" / name,
        CLAUDE_DIR / "statusline.sh",
        CURSOR_DIR / "rules" / name,
        CURSOR_DIR / "commands" / name,
    ]


def _legacy_store() -> dict:
    """In-memory store adopting pre-record links via the retired heuristic.

    Only consulted while the record file does not exist yet; never writes.
    """
    # Deferred import to avoid a top-level cycle (filesystem imports this
    # module for record_symlink/forget_symlink/is_our_symlink support).
    from .filesystem import get_symlink_target, is_symlink

    data = _empty_store()
    for candidate in _legacy_candidate_paths():
        if not is_symlink(candidate):
            continue
        target = get_symlink_target(candidate)
        if target is None:
            continue
        target_str = str(target)
        if any(substr in target_str for substr in _LEGACY_SUBSTRINGS):
            data["links"][_key(candidate)] = {
                "source": target_str,
                "recordedAt": _now_iso(),
            }
    return data
