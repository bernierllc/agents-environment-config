"""Atomic JSON file writing for AEC.

Stub module -- real implementation lives on a separate branch.
"""

from pathlib import Path


def atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically using write-then-rename pattern."""
    raise NotImplementedError("Stub -- real implementation on feature branch")
