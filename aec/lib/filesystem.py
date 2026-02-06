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

    # Remove existing target if it's a symlink
    if target.is_symlink():
        target.unlink()
    elif target.exists():
        # Target exists and is not a symlink - don't overwrite
        return False

    if IS_WINDOWS:
        return _create_windows_link(source, target, is_directory)
    else:
        return _create_unix_symlink(source, target)


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

    if not path.exists() and not path.is_symlink():
        return False

    if IS_WINDOWS:
        # On Windows, junctions are removed differently
        if path.is_dir():
            try:
                # Use rmdir for junctions
                subprocess.run(
                    ["cmd", "/c", "rmdir", str(path)],
                    capture_output=True,
                )
                return True
            except Exception:
                pass

    # Standard removal
    try:
        if path.is_symlink():
            path.unlink()
            return True
        return False
    except Exception:
        return False


def is_symlink(path: Path) -> bool:
    """
    Check if path is a symlink (or junction on Windows).
    """
    path = Path(path)

    if path.is_symlink():
        return True

    # On Windows, also check for junctions
    if IS_WINDOWS and path.is_dir():
        try:
            # Check if it's a reparse point (junction)
            import ctypes
            from ctypes import wintypes

            FILE_ATTRIBUTE_REPARSE_POINT = 0x400
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
            if attrs != -1:
                return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)
        except Exception:
            pass

    return False


def is_our_symlink(path: Path) -> bool:
    """
    Check if a symlink was created by us (points to aec content).

    Args:
        path: The path to check

    Returns:
        True if it's a symlink pointing to agents-environment-config content
    """
    if not is_symlink(path):
        return False

    try:
        target = get_symlink_target(path)
        if target is None:
            return False

        target_str = str(target)
        return (
            "agents-environment-config" in target_str
            or ".agent-tools" in target_str
        )
    except Exception:
        return False


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
    if IS_WINDOWS and path.is_dir():
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
