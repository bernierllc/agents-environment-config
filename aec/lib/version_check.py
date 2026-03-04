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
