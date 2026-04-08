"""Report viewer detection and selection for quality reports."""

import platform
import shutil
from typing import Any, Dict, List, Optional


REPORT_VIEWERS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "darwin": {
        "cursor": {
            "display_name": "Cursor",
            "command": "cursor {file}",
            "detect": ["cursor"],
        },
        "vscode": {
            "display_name": "VS Code",
            "command": "code {file}",
            "detect": ["code"],
        },
        "open": {
            "display_name": "Default App (open)",
            "command": "open {file}",
            "detect": None,  # always available on macOS
        },
        "nano": {
            "display_name": "nano",
            "command": "nano {file}",
            "detect": ["nano"],
        },
        "vim": {
            "display_name": "vim",
            "command": "vim {file}",
            "detect": ["vim"],
        },
    },
    "linux": {
        "vscode": {
            "display_name": "VS Code",
            "command": "code {file}",
            "detect": ["code"],
        },
        "xdg": {
            "display_name": "Default App (xdg-open)",
            "command": "xdg-open {file}",
            "detect": ["xdg-open"],
        },
        "nano": {
            "display_name": "nano",
            "command": "nano {file}",
            "detect": ["nano"],
        },
        "vim": {
            "display_name": "vim",
            "command": "vim {file}",
            "detect": ["vim"],
        },
    },
    "windows": {
        "vscode": {
            "display_name": "VS Code",
            "command": "code {file}",
            "detect": ["code"],
        },
        "notepad": {
            "display_name": "Notepad",
            "command": "notepad {file}",
            "detect": None,  # always available
        },
        "start": {
            "display_name": "Default App",
            "command": "start {file}",
            "detect": None,
        },
    },
}


def get_platform_key() -> str:
    """Return the platform key for REPORT_VIEWERS lookup.

    Maps platform.system() to dict keys:
    - "Darwin" -> "darwin"
    - "Linux" -> "linux"
    - "Windows" -> "windows"

    Returns "linux" as fallback for unknown platforms.
    """
    system = platform.system()
    mapping = {
        "Darwin": "darwin",
        "Linux": "linux",
        "Windows": "windows",
    }
    return mapping.get(system, "linux")


def detect_viewers(platform_key: Optional[str] = None) -> List[Dict[str, str]]:
    """Detect available report viewers on the current OS.

    Args:
        platform_key: Platform key to look up in REPORT_VIEWERS.
            If None, auto-detects via get_platform_key().

    Returns:
        List of dicts with keys: key, display_name, command.
        Viewers with detect=None are always included.
        Others are included only if shutil.which() finds one of their commands.
    """
    if platform_key is None:
        platform_key = get_platform_key()

    viewers = REPORT_VIEWERS.get(platform_key, {})
    available = []

    for key, config in viewers.items():
        detect_commands = config["detect"]
        is_available = detect_commands is None or any(
            shutil.which(cmd) is not None for cmd in detect_commands
        )

        if is_available:
            available.append({
                "key": key,
                "display_name": config["display_name"],
                "command": config["command"],
            })

    return available


def get_viewer_command(
    viewer_key: str, platform_key: Optional[str] = None
) -> Optional[str]:
    """Get the command string for a viewer key.

    Args:
        viewer_key: The viewer identifier (e.g. "vscode", "nano").
        platform_key: Platform key to look up. If None, auto-detects.

    Returns:
        Command string containing {file} placeholder, or None if not found.
    """
    if platform_key is None:
        platform_key = get_platform_key()

    viewers = REPORT_VIEWERS.get(platform_key, {})
    config = viewers.get(viewer_key)

    if config is None:
        return None

    return config["command"]


def format_viewer_command(command: str, file_path: str) -> str:
    """Replace {file} placeholder in a command string with an actual file path.

    Args:
        command: Command template containing {file} placeholder.
        file_path: Actual file path to substitute.

    Returns:
        Command string with {file} replaced by the file path.
    """
    return command.replace("{file}", file_path)
