"""OS-specific scheduler wrappers for AEC test runner."""

from pathlib import Path
from typing import Optional


def get_scheduler():
    """Return the appropriate scheduler module for the current platform."""
    from aec.lib.config import IS_MACOS, IS_LINUX, IS_WINDOWS

    if IS_MACOS:
        from . import macos

        return macos
    elif IS_WINDOWS:
        from . import windows

        return windows
    else:
        from . import linux

        return linux
