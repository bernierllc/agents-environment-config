"""Version check: detect when a newer AEC release is available on GitHub."""

import json
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from .config import VERSION, AEC_HOME, get_repo_root

# GitHub API endpoint for latest release
GITHUB_RELEASES_URL = (
    "https://api.github.com/repos/bernierllc/agents-environment-config/releases/latest"
)

# Cache location and TTL
VERSION_CACHE_FILE = AEC_HOME / "version-check.json"
CACHE_TTL = timedelta(days=7)


def parse_version(version_string: str) -> tuple:
    """Parse a version string like 'v2.1.0' or '2.1.0' into a comparable tuple."""
    return tuple(int(part) for part in version_string.lstrip("v").split("."))


def _read_cache() -> Optional[dict]:
    """Read cached version check result. Returns None if missing, stale, or corrupt."""
    try:
        if not VERSION_CACHE_FILE.exists():
            return None
        data = json.loads(VERSION_CACHE_FILE.read_text())
        last_check = datetime.fromisoformat(data["last_check"])
        if datetime.now(timezone.utc) - last_check > CACHE_TTL:
            return None
        return data
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        return None


def _write_cache(latest_version: str, release_url: str) -> None:
    """Write version check result to cache file."""
    try:
        VERSION_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "last_check": datetime.now(timezone.utc).isoformat(),
            "latest_version": latest_version,
            "release_url": release_url,
        }
        VERSION_CACHE_FILE.write_text(json.dumps(data, indent=2) + "\n")
    except OSError:
        pass  # Cache write failure is non-critical
