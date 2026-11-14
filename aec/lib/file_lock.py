"""Exclusive lock on a file, shared by AEC processes on Windows, macOS and Linux.

The OS drops the lock when the holding process exits, so a crash never leaves
a stale lock behind. Not reentrant: never take the same lock twice in one process.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:
    import fcntl

    msvcrt = None
except ImportError:  # Windows
    fcntl = None
    import msvcrt


@contextmanager
def locked(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+") as lock_fp:
        if fcntl is not None:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
        else:
            lock_fp.seek(0)
            # LK_LOCK retries for ~10s, then raises OSError (callers handle it).
            msvcrt.locking(lock_fp.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
            else:
                lock_fp.seek(0)
                msvcrt.locking(lock_fp.fileno(), msvcrt.LK_UNLCK, 1)
