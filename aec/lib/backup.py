"""Backup utilities for AEC discovery.

Stub module -- real implementation lives on a separate branch.
"""

from pathlib import Path


def backup_item(item_path: Path, repo_path: Path) -> Path:
    """Back up a local item before replacing with AEC version."""
    raise NotImplementedError("Stub -- real implementation on feature branch")


def ensure_backup_gitignore(repo_path: Path) -> None:
    """Ensure .aec-backup/ is in .gitignore."""
    raise NotImplementedError("Stub -- real implementation on feature branch")
