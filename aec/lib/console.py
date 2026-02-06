"""Cross-platform colored console output."""

import platform
import sys
from typing import Optional

# Enable ANSI colors on Windows 10+
if platform.system() == "Windows":
    try:
        import os
        os.system("")  # Enables ANSI escape sequences in Windows terminal

        # Also try to enable via Windows API for older terminals
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass  # Fall back to no colors if this fails


class Console:
    """
    Colored console output that works on macOS, Linux, and Windows.

    Usage:
        Console.header("Setup")
        Console.success("File created")
        Console.error("Something failed")
        Console.warning("Check this")
        Console.info("FYI")
    """

    # ANSI color codes
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"
    MAGENTA = "\033[0;35m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    NC = "\033[0m"  # No Color / Reset

    # Check if we should use colors
    _use_colors: Optional[bool] = None

    @classmethod
    def _should_use_colors(cls) -> bool:
        """Determine if we should output colors."""
        if cls._use_colors is not None:
            return cls._use_colors

        # Check NO_COLOR environment variable (standard)
        import os
        if os.environ.get("NO_COLOR"):
            cls._use_colors = False
            return False

        # Check if stdout is a TTY
        if not sys.stdout.isatty():
            cls._use_colors = False
            return False

        cls._use_colors = True
        return True

    @classmethod
    def _colorize(cls, color: str, text: str) -> str:
        """Apply color if colors are enabled."""
        if cls._should_use_colors():
            return f"{color}{text}{cls.NC}"
        return text

    @classmethod
    def success(cls, msg: str, indent: int = 2) -> None:
        """Print a success message with green checkmark."""
        prefix = " " * indent
        symbol = cls._colorize(cls.GREEN, "✓")
        print(f"{prefix}{symbol} {msg}")

    @classmethod
    def error(cls, msg: str, indent: int = 2) -> None:
        """Print an error message with red X."""
        prefix = " " * indent
        symbol = cls._colorize(cls.RED, "✗")
        print(f"{prefix}{symbol} {msg}")

    @classmethod
    def warning(cls, msg: str, indent: int = 2) -> None:
        """Print a warning message with yellow symbol."""
        prefix = " " * indent
        symbol = cls._colorize(cls.YELLOW, "⚠")
        print(f"{prefix}{symbol} {msg}")

    @classmethod
    def info(cls, msg: str, indent: int = 2) -> None:
        """Print an info message with blue symbol."""
        prefix = " " * indent
        symbol = cls._colorize(cls.BLUE, "ℹ")
        print(f"{prefix}{symbol} {msg}")

    @classmethod
    def skip(cls, msg: str, indent: int = 2) -> None:
        """Print a skipped item message."""
        prefix = " " * indent
        symbol = cls._colorize(cls.YELLOW, "⚠")
        print(f"{prefix}{symbol} {msg}")

    @classmethod
    def header(cls, msg: str) -> None:
        """Print a section header."""
        colored = cls._colorize(cls.BLUE, f"=== {msg} ===")
        print(f"\n{colored}\n")

    @classmethod
    def subheader(cls, msg: str) -> None:
        """Print a subsection header."""
        colored = cls._colorize(cls.BLUE, msg)
        print(f"\n{colored}\n")

    @classmethod
    def path(cls, path: str) -> str:
        """Format a path with color."""
        return cls._colorize(cls.GREEN, str(path))

    @classmethod
    def cmd(cls, command: str) -> str:
        """Format a command with color."""
        return cls._colorize(cls.CYAN, command)

    @classmethod
    def version(cls, ver: str) -> str:
        """Format a version string with color."""
        return cls._colorize(cls.CYAN, ver)

    @classmethod
    def dim(cls, text: str) -> str:
        """Dim text (for less important info)."""
        return cls._colorize(cls.DIM, text)

    @classmethod
    def bold(cls, text: str) -> str:
        """Bold text."""
        return cls._colorize(cls.BOLD, text)

    @classmethod
    def print(cls, msg: str = "", **kwargs) -> None:
        """Print a plain message (supports print() kwargs like end, sep)."""
        print(msg, **kwargs)

    @classmethod
    def newline(cls) -> None:
        """Print an empty line."""
        print()
