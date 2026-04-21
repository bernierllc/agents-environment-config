"""Backup-before-replace: copies originals to .aec-backup/ with timestamped names."""

import shutil
from datetime import datetime, timezone
from pathlib import Path

BACKUP_DIR_NAME = ".aec-backup"
BACKUP_GITIGNORE_ENTRY = ".aec-backup/"


def _timestamp_suffix() -> str:
    """Return current UTC time as YYYY-MM-DDTHH-MM-SS."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")


def backup_item(item_path: Path, repo_path: Path) -> Path:
    """Copy a file or directory to .aec-backup/ with a timestamped name.

    Files become: .aec-backup/<stem>.<timestamp>.<ext>
    Directories become: .aec-backup/<name>.<timestamp>/

    Args:
        item_path: Path to the file or directory to back up.
        repo_path: Path to the repository root (backup dir lives here).

    Returns:
        Path to the backup copy.
    """
    backup_dir = repo_path / BACKUP_DIR_NAME
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = _timestamp_suffix()

    if item_path.is_dir():
        backup_path = backup_dir / f"{item_path.name}.{timestamp}"
        shutil.copytree(item_path, backup_path)
    else:
        stem = item_path.stem
        suffix = item_path.suffix
        backup_path = backup_dir / f"{stem}.{timestamp}{suffix}"
        shutil.copy2(item_path, backup_path)

    return backup_path


def ensure_backup_gitignore(repo_path: Path) -> None:
    """Ensure .aec-backup/ is listed in the repo's .gitignore.

    Handles three cases:
    - No .gitignore exists: creates one with the entry.
    - .gitignore exists but doesn't have the entry: appends it.
    - Entry already present: no-op.
    """
    gitignore_path = repo_path / ".gitignore"

    if gitignore_path.exists():
        content = gitignore_path.read_text()
        # Check if the entry is already present as a standalone line
        lines = content.splitlines()
        if BACKUP_GITIGNORE_ENTRY in lines:
            return
        # Append with a newline separator if content doesn't end with one
        if content and not content.endswith("\n"):
            content += "\n"
        content += BACKUP_GITIGNORE_ENTRY + "\n"
        gitignore_path.write_text(content)
    else:
        gitignore_path.write_text(BACKUP_GITIGNORE_ENTRY + "\n")


def list_backups(repo_path: Path) -> list[Path]:
    """Return a sorted list of all items in .aec-backup/.

    Returns an empty list if the backup directory does not exist.
    """
    backup_dir = repo_path / BACKUP_DIR_NAME
    if not backup_dir.exists():
        return []
    return sorted(backup_dir.iterdir())
