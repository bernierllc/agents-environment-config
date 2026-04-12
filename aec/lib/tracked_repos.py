"""Tracked repos store -- JSON replacement for setup-repo-locations.txt."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .atomic_write import atomic_write_json


def _tracked_repos_path() -> Path:
    """Return the path to tracked-repos.json, computed dynamically."""
    return Path.home() / ".agents-environment-config" / "tracked-repos.json"


def _setup_log_path() -> Path:
    """Return the path to the legacy setup-repo-locations.txt."""
    return Path.home() / ".agents-environment-config" / "setup-repo-locations.txt"


def _empty_store() -> dict:
    """Return a fresh empty tracked-repos store."""
    return {"schemaVersion": 1, "repos": {}}


def load_tracked_repos() -> dict:
    """Read tracked-repos.json, returning empty store on missing/corrupt.

    If the JSON file doesn't exist but the legacy txt file does,
    automatically migrates entries before returning.
    """
    json_path = _tracked_repos_path()

    if not json_path.exists():
        txt_path = _setup_log_path()
        if txt_path.exists():
            migrate_from_txt()
            # Re-read after migration
            if json_path.exists():
                return _read_json(json_path)
        return _empty_store()

    return _read_json(json_path)


def _read_json(path: Path) -> dict:
    """Read and validate the JSON file, returning empty store on error."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "repos" not in data:
            return _empty_store()
        return data
    except (json.JSONDecodeError, OSError):
        return _empty_store()


def save_tracked_repos(data: dict) -> None:
    """Write tracked-repos.json atomically."""
    atomic_write_json(_tracked_repos_path(), data)


def add_tracked_repo(repo_path: Path, aec_version: str) -> None:
    """Add a repo entry with aecJsonPath, trackedAt, and aecVersion."""
    data = load_tracked_repos()
    abs_path = str(Path(repo_path).resolve())
    data["repos"][abs_path] = {
        "aecJsonPath": str(Path(repo_path).resolve() / ".aec.json"),
        "trackedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "aecVersion": aec_version,
    }
    save_tracked_repos(data)


def remove_tracked_repo(repo_path: Path) -> None:
    """Remove a repo entry by path."""
    data = load_tracked_repos()
    abs_path = str(Path(repo_path).resolve())
    data["repos"].pop(abs_path, None)
    save_tracked_repos(data)


def is_tracked(repo_path: Path) -> bool:
    """Check if a path is in the tracked repos store."""
    data = load_tracked_repos()
    abs_path = str(Path(repo_path).resolve())
    return abs_path in data["repos"]


def get_all_tracked_paths() -> list[Path]:
    """Return all tracked repo paths that exist on disk."""
    data = load_tracked_repos()
    result = []
    for path_str in data["repos"]:
        p = Path(path_str)
        if p.exists():
            result.append(p)
    return sorted(result)


def migrate_from_txt() -> int:
    """Migrate entries from setup-repo-locations.txt to tracked-repos.json.

    Reads the legacy pipe-delimited text file, converts each entry to the
    JSON schema, and writes the result. Returns the count of migrated entries.
    """
    txt_path = _setup_log_path()
    if not txt_path.exists():
        return 0

    content = txt_path.read_text().strip()
    if not content:
        return 0

    data = _empty_store()
    count = 0

    for line in content.split("\n"):
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            timestamp = parts[0]
            version = parts[1]
            path_str = str(Path(parts[2]).resolve())
            data["repos"][path_str] = {
                "aecJsonPath": str(Path(path_str) / ".aec.json"),
                "trackedAt": timestamp,
                "aecVersion": version,
            }
            count += 1

    if count > 0:
        save_tracked_repos(data)

    return count
