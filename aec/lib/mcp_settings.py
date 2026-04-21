"""Read/write mcpServers entries in Claude Code settings.json.

Performs idempotent, non-destructive read-modify-write: only the mcpServers
key is touched; all other settings.json content is preserved.
"""

import json
from pathlib import Path

from .atomic_write import atomic_write_json
from .scope import Scope


def get_settings_path(scope: Scope) -> Path:
    """Return the settings.json path for the given scope."""
    if scope.is_global:
        return Path.home() / ".claude" / "settings.json"
    assert scope.repo_path is not None
    return scope.repo_path / ".claude" / "settings.json"


def read_mcp_servers(settings_path: Path) -> dict:
    """Return the current mcpServers dict, or {} if absent or unreadable."""
    if not settings_path.exists():
        return {}
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        return dict(data.get("mcpServers", {}))
    except (json.JSONDecodeError, OSError):
        return {}


def write_mcp_server(settings_path: Path, name: str, entry: dict) -> None:
    """Merge entry under mcpServers.<name>. Creates file/key if absent. Idempotent."""
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}
    data.setdefault("mcpServers", {})[name] = entry
    atomic_write_json(settings_path, data)


def remove_mcp_server(settings_path: Path, name: str) -> bool:
    """Remove mcpServers.<name>. Returns True if the entry existed and was removed."""
    if not settings_path.exists():
        return False
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    mcp_servers = data.get("mcpServers", {})
    if name not in mcp_servers:
        return False
    del mcp_servers[name]
    if not mcp_servers:
        data.pop("mcpServers", None)
    atomic_write_json(settings_path, data)
    return True
