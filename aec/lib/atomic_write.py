"""Atomic JSON file writer -- write-tmp-then-rename for crash safety."""

import json
import os
from pathlib import Path


def atomic_write_text(path: Path, content: str) -> None:
    """Write content to path atomically via tmp-then-rename.

    Creates parent directories if needed. Uses os.replace() for an atomic
    rename that works on both POSIX and Windows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
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
