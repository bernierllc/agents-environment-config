"""Prerequisite checking for test suite execution."""

import shutil
import subprocess
from typing import Any, Dict, List, Tuple

# Registry of known prerequisites and how to check them.
# Each entry has:
#   display_name: Human-readable name
#   check: callable that returns (available: bool, detail: str)
PREREQUISITE_CHECKS: Dict[str, Dict[str, Any]] = {
    "docker": {
        "display_name": "Docker",
        "check": lambda: _check_docker(),
    },
    "node": {
        "display_name": "Node.js",
        "check": lambda: _check_command("node"),
    },
    "npm": {
        "display_name": "npm",
        "check": lambda: _check_command("npm"),
    },
    "python": {
        "display_name": "Python",
        "check": lambda: _check_command_with_fallback("python3", "python"),
    },
    "pip": {
        "display_name": "pip",
        "check": lambda: _check_command_with_fallback("pip3", "pip"),
    },
    "cargo": {
        "display_name": "Cargo (Rust)",
        "check": lambda: _check_command("cargo"),
    },
    "go": {
        "display_name": "Go",
        "check": lambda: _check_command("go"),
    },
    "ruby": {
        "display_name": "Ruby",
        "check": lambda: _check_command("ruby"),
    },
    "bundle": {
        "display_name": "Bundler (Ruby)",
        "check": lambda: _check_command("bundle"),
    },
}


def _check_command(name: str) -> Tuple[bool, str]:
    """Check if a command is available on PATH.

    Returns (True, "/path/to/command") or (False, "not found on PATH").
    """
    path = shutil.which(name)
    if path:
        return (True, path)
    return (False, "not found on PATH")


def _check_command_with_fallback(
    primary: str, fallback: str,
) -> Tuple[bool, str]:
    """Check primary command, falling back to secondary if not found."""
    available, detail = _check_command(primary)
    if available:
        return (available, detail)
    return _check_command(fallback)


def _check_docker() -> Tuple[bool, str]:
    """Check that docker command exists AND daemon is running.

    Returns (True, "Docker running"), (False, "docker command not found"),
    or (False, "Docker not running").
    """
    if not shutil.which("docker"):
        return (False, "docker command not found")
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return (True, "Docker running")
        return (False, "Docker not running")
    except (subprocess.SubprocessError, OSError):
        return (False, "Docker not running")


def check_prerequisite(name: str) -> Tuple[bool, str]:
    """Check a single prerequisite by name.

    If name is in the registry, uses the registered check.
    Otherwise falls back to checking if the name is a command on PATH.
    """
    entry = PREREQUISITE_CHECKS.get(name)
    if entry:
        return entry["check"]()
    return _check_command(name)


def check_prerequisites(names: List[str]) -> List[Tuple[str, bool, str]]:
    """Check multiple prerequisites.

    Returns list of (name, available, detail) tuples in input order.
    """
    results: List[Tuple[str, bool, str]] = []
    for name in names:
        available, detail = check_prerequisite(name)
        results.append((name, available, detail))
    return results
