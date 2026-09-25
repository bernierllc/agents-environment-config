"""Atomic JSON file writer -- write-tmp-then-rename for crash safety."""

import json
import os
from pathlib import Path


def atomic_write_text(path: Path, content: str) -> None:
    """Write content to path atomically via tmp-then-rename.

    Creates parent directories if needed and preserves an existing file's
    permission bits. Uses os.replace() for an atomic rename that works on
    both POSIX and Windows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        # Create the tmp file with the original's mode (e.g. 0600 settings)
        # before any content lands in it, so it is never briefly readable.
        mode = path.stat().st_mode & 0o7777 if path.exists() else 0o666
        tmp_path.unlink(missing_ok=True)
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            if path.exists() and hasattr(os, "fchmod"):  # no fchmod on Windows <3.13
                os.fchmod(f.fileno(), mode)  # umask may have stripped bits
            f.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        # Clean up the tmp file on any failure
        tmp_path.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, data: dict) -> None:
    """Write a dict as formatted JSON to path atomically.

    Format matches codebase convention: 2-space indent, trailing newline, utf-8.
    """
    atomic_write_text(path, json.dumps(data, indent=2) + "\n")
