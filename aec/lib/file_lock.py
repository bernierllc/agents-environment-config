"""Exclusive lock on a file, shared by AEC processes on Windows, macOS and Linux.

The OS drops the lock when the holding process exits, so a crash never leaves
a stale lock behind. Not reentrant: never take the same lock twice in one process.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import IO, Iterator, Optional

try:
    import fcntl

    msvcrt = None
except ImportError:  # Windows
    fcntl = None
    import msvcrt


def acquire(lock_path: Path, blocking: bool = True) -> Optional[IO]:
    """Take the lock; returns the handle to pass to release(), or None when
    blocking is False and another handle holds it."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fp = open(lock_path, "a+")
    try:
        if fcntl is not None:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        else:
            lock_fp.seek(0)
            # LK_LOCK retries for ~10s, then raises OSError (callers handle it).
            msvcrt.locking(lock_fp.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
    except OSError:
        lock_fp.close()
        if blocking:
            raise
        return None  # held elsewhere: the answer the caller asked for
    return lock_fp


def release(lock_fp: IO) -> None:
    try:
        if fcntl is not None:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
        else:
            lock_fp.seek(0)
            msvcrt.locking(lock_fp.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        lock_fp.close()


def is_held(lock_path: Path) -> bool:
    """True if another handle holds the lock right now."""
    if not lock_path.exists():
        return False
    lock_fp = acquire(lock_path, blocking=False)
    if lock_fp is None:
        return True
    release(lock_fp)
    return False


@contextmanager
def locked(lock_path: Path) -> Iterator[None]:
    lock_fp = acquire(lock_path)
    try:
        yield
    finally:
        release(lock_fp)
