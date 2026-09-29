"""Cross-platform filesystem operations."""

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Union

from .config import IS_WINDOWS


def create_symlink(
    source: Path,
    target: Path,
    is_directory: Optional[bool] = None,
) -> bool:
    """
    Create a symlink/junction that works on both platforms.

    On Windows:
    - Uses directory junctions for directories (no admin required)
    - Uses file symlinks or falls back to copy for files

    On macOS/Linux:
    - Uses standard symlinks

    Args:
        source: The path that the symlink should point TO (must exist)
        target: The path where the symlink will be created
        is_directory: Whether source is a directory. Auto-detected if None.

    Returns:
        True if successful, False otherwise
    """
    source = Path(source).resolve()
    target = Path(target)

    # Auto-detect if source is a directory
    if is_directory is None:
        is_directory = source.is_dir()

    # Ensure parent directory exists
    target.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing target if it's a symlink (or junction, even a broken one)
    if is_symlink(target):
        if not remove_symlink(target):
            return False
    elif target.exists():
        # Target exists and is not a symlink - don't overwrite
        return False

    if IS_WINDOWS:
        created = _create_windows_link(source, target, is_directory)
    else:
        created = _create_unix_symlink(source, target)

    if created:
        from .managed_symlinks import record_symlink
        try:
            record_symlink(target, source)
        except OSError:
            # An unrecorded link is one AEC can never recognise or repair:
            # undo it and report failure rather than leave it half-managed.
            if not remove_symlink(target):
                target.unlink(missing_ok=True)  # Windows copy fallback
            return False

    return created


def _create_windows_link(source: Path, target: Path, is_directory: bool) -> bool:
    """Create Windows junction (dirs) or symlink (files)."""
    if is_directory:
        # Use mklink /J for junctions (no admin required)
        try:
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(target), str(source)],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False
    else:
        # Try symlink for files, fall back to copy
        try:
            target.symlink_to(source)
            return True
        except OSError:
            # Symlink failed (probably no admin), fall back to copy
            try:
                shutil.copy2(source, target)
                return True
            except Exception:
                return False


def _create_unix_symlink(source: Path, target: Path) -> bool:
    """Create Unix symlink."""
    try:
        target.symlink_to(source)
        return True
    except Exception:
        return False


def remove_symlink(path: Path) -> bool:
    """
    Remove a symlink (or junction on Windows).

    Args:
        path: The symlink to remove

    Returns:
        True if removed, False if not a symlink or removal failed
    """
    path = Path(path)

    if not path.exists() and not is_symlink(path):
        return False

    if IS_WINDOWS:
        # On Windows, junctions are removed differently
        if _is_junction(path):
            try:
                # Use rmdir for junctions
                result = subprocess.run(
                    ["cmd", "/c", "rmdir", str(path)],
                    capture_output=True,
                )
                if result.returncode == 0:
                    _forget_symlink(path)
                    return True
            except Exception:
                pass

    # Standard removal
    try:
        if path.is_symlink():
            path.unlink()
            _forget_symlink(path)
            return True
        return False
    except Exception:
        return False


def _forget_symlink(path: Path) -> None:
    """Drop path from AEC's managed-symlink ownership record, if present."""
    from .managed_symlinks import forget_symlink
    try:
        forget_symlink(path)
    except OSError:
        pass  # link is gone; a leftover entry can't match a new link's target


def is_symlink(path: Path) -> bool:
    """
    Check if path is a symlink (or junction on Windows).
    """
    path = Path(path)

    return path.is_symlink() or _is_junction(path)


def _is_junction(path: Path) -> bool:
    """True for a Windows reparse point (junction), even one whose target is gone.

    lstat doesn't follow the link, so a junction left dangling by a moved
    checkout is still detected -- path.is_dir() would follow it and say no.
    """
    if not IS_WINDOWS:
        return False
    try:
        attrs = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT


def is_our_symlink(path: Path) -> bool:
    """
    Check if a symlink was created by AEC.

    Ownership is a lookup in AEC's managed-symlink record
    (~/.agents-environment-config/managed-symlinks.json), written by
    create_symlink() at creation time -- not a heuristic on the link's
    target. A checkout cloned under a non-standard name, or moved/recloned
    after linking, is still recognised as ours: the record is keyed by the
    link's own path, and the link must still point at the recorded source
    (so a user's replacement link at the same path is not claimed).

    Pre-existing links from before this record existed are adopted via the
    retired substring heuristic until the first record write persists them
    (see aec.lib.managed_symlinks). This check never writes.

    Args:
        path: The path to check

    Returns:
        True if AEC's record shows it owns this symlink.
    """
    if not is_symlink(path):
        return False

    from .managed_symlinks import normalize_target, recorded_source

    source = recorded_source(path)
    target = get_symlink_target(path)
    if source is None or target is None:
        return False
    # Path-only membership isn't enough: a user may have replaced AEC's link
    # with their own at the same path. It's ours only if it still points
    # where we pointed it (even if that checkout has since moved away).
    return normalize_target(path, str(target)) == normalize_target(path, source)


def get_symlink_target(path: Path) -> Optional[Path]:
    """
    Get the target of a symlink.

    Args:
        path: The symlink path

    Returns:
        The target path, or None if not a symlink
    """
    path = Path(path)

    if path.is_symlink():
        try:
            return Path(os.readlink(path))
        except Exception:
            pass

    # On Windows, try to read junction target
    if _is_junction(path):
        try:
            # os.readlink reads junctions (Python 3.8+); strip the \\?\ prefix.
            target = os.readlink(path)
            return Path(target[4:] if target.startswith("\\\\?\\") else target)
        except OSError:
            pass
        try:
            result = subprocess.run(
                ["cmd", "/c", "dir", "/al", str(path.parent)],
                capture_output=True,
                text=True,
            )
            # Parse output to find junction target
            for line in result.stdout.split("\n"):
                if path.name in line and "[" in line:
                    # Extract target from [target] format
                    start = line.find("[") + 1
                    end = line.find("]")
                    if start > 0 and end > start:
                        return Path(line[start:end])
        except Exception:
            pass

    return None


def ensure_directory(path: Path) -> None:
    """
    Create directory if it doesn't exist.

    Args:
        path: Directory path to create
    """
    Path(path).mkdir(parents=True, exist_ok=True)


def copy_file(source: Path, target: Path, overwrite: bool = False) -> bool:
    """
    Copy a file from source to target.

    Args:
        source: Source file path
        target: Target file path
        overwrite: Whether to overwrite existing files

    Returns:
        True if copied, False if skipped or failed
    """
    source = Path(source)
    target = Path(target)

    if not source.exists():
        return False

    if target.exists() and not overwrite:
        return False

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return True
    except Exception:
        return False


def safe_path_str(path: Path) -> str:
    """
    Get a string representation of a path that's safe for the current platform.

    Args:
        path: The path to convert

    Returns:
        String representation with correct separators
    """
    return str(Path(path))


def resolve_installed_path(target_dir: Path, name: str) -> Path:
    """Find the actual on-disk path for an installed item.

    Checks for both the bare name and name.md to handle files installed
    before extension preservation was added.

    Args:
        target_dir: Directory containing installed items.
        name: The manifest key (stem without extension).

    Returns:
        The existing path if found; otherwise ``target_dir / name``.
    """
    direct = target_dir / name
    if direct.exists():
        return direct
    md_path = target_dir / (name + ".md")
    if md_path.exists():
        return md_path
    return direct


def installed_dst_path(target_dir: Path, name: str, src: Path) -> Path:
    """Compute the destination path for an item being installed.

    For file items (agents, rules) the source extension is preserved so that
    Claude Code can discover the file. For directory items (skills) the bare
    name is used unchanged.

    Args:
        target_dir: Directory to install into.
        name: The manifest key (stem without extension).
        src: The source path being installed from.

    Returns:
        ``target_dir / name`` for directories, ``target_dir / (name + src.suffix)``
        for files.
    """
    if src.is_dir():
        return target_dir / name
    return target_dir / (name + src.suffix)


def remove_installed_item(path: Path) -> None:
    """Delete an installed item (dir or file), refusing anything inside the aec catalog.

    Every install, upgrade and uninstall path removes the old copy before
    writing the new one. Inside the catalog repo that copy *is* the source, so
    the guard sits here, at the delete, rather than in each caller.
    """
    from .config import get_repo_root

    root = get_repo_root()
    resolved = path.resolve()
    if root is not None and (resolved == root.resolve() or root.resolve() in resolved.parents):
        raise RuntimeError(
            f"refusing to delete {path}: it is inside the aec catalog ({root}), "
            "so it is an install source, not an installed copy"
        )
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()
