"""Check that the MCP servers a user requires are registered in every installed agent client.

The required set is the ``required_mcp_servers`` list under preferences ``settings`` (empty by
default, so a first-time user sees no check). Each installed client is checked on its own config:

- Claude Code: ``mcpServers`` in ``~/.claude.json`` or ``~/.claude/settings.json``
- Cursor: ``mcpServers`` in ``~/.cursor/mcp.json``
- Codex: a ``[mcp_servers.<name>]`` table in ``~/.codex/config.toml`` (parsed with tomllib/tomli)

A client counts as installed when its config directory or file exists. A server registered with a
``command`` (stdio) must point at an executable that exists; a ``url`` entry needs no local binary.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

REQUIRED_MCP_SETTING = "required_mcp_servers"


def required_servers(settings_value: Any) -> List[str]:
    """Normalise the preference value to a de-duplicated list of server names.

    Raises ValueError for a value that is set but malformed, so a typo cannot silently turn the
    check off.
    """
    if settings_value is None:
        return []
    if not isinstance(settings_value, list) or not all(
        isinstance(s, str) and s.strip() for s in settings_value
    ):
        raise ValueError("must be a list of non-empty server names")
    return list(dict.fromkeys(s.strip() for s in settings_value))


def _json_servers(path: Path) -> Optional[Dict[str, Any]]:
    """The mcpServers dict of a JSON config, or None when the file cannot be read (unverifiable)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    servers = data.get("mcpServers", {}) if isinstance(data, dict) else {}
    return servers if isinstance(servers, dict) else {}


def _codex_servers(path: Path) -> Optional[Dict[str, Any]]:
    """The mcp_servers table of a Codex config.toml, or None when the file cannot be parsed."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, ValueError):  # ValueError covers TOMLDecodeError and UnicodeDecodeError
        return None
    servers = data.get("mcp_servers", {})
    return servers if isinstance(servers, dict) else {}


def _command_problem(command: str) -> Optional[str]:
    resolved = command if os.path.isabs(command) else shutil.which(command)
    if not resolved or not os.path.isfile(resolved):
        return "command %s does not exist" % command
    if not os.access(resolved, os.X_OK):
        return "command %s is not executable" % command
    return None


def _entry_problem(entry: Any) -> Optional[str]:
    """Why a registered entry cannot work, or None when it looks usable."""
    if not isinstance(entry, dict):
        return "entry is not a table"
    if entry.get("disabled") is True or entry.get("enabled") is False:
        return "entry is disabled"
    command = entry.get("command")
    if command:
        return _command_problem(str(command))
    if entry.get("url"):
        return None
    return "entry has neither command nor url"


def check_required_mcp_servers(required: List[str], home: Path) -> List[str]:
    """One message per (client, server) that is missing or unusable; empty when all is well."""
    problems: List[str] = []
    claude_files = [home / ".claude.json", home / ".claude" / "settings.json"]
    cursor_file = home / ".cursor" / "mcp.json"
    codex_file = home / ".codex" / "config.toml"

    claude_installed = (home / ".claude").exists() or claude_files[0].exists()
    if claude_installed:
        merged: Dict[str, Any] = {}
        unreadable = False
        for f in claude_files:
            if not f.exists():
                continue
            servers = _json_servers(f)
            if servers is None:
                problems.append("Claude Code: cannot read %s, so required MCP servers are unverified" % f.name)
                unreadable = True
                continue
            merged.update(servers)
        for name in ([] if unreadable else required):
            if name not in merged:
                problems.append("Claude Code: MCP server '%s' is not registered (~/.claude.json mcpServers)" % name)
            elif _entry_problem(merged[name]):
                problems.append("Claude Code: MCP server '%s' is broken: %s" % (name, _entry_problem(merged[name])))

    if (home / ".cursor").exists():
        servers = _json_servers(cursor_file) if cursor_file.exists() else {}
        if servers is None:
            problems.append("Cursor: cannot read mcp.json, so required MCP servers are unverified")
        else:
            for name in required:
                if name not in servers:
                    problems.append("Cursor: MCP server '%s' is not registered (~/.cursor/mcp.json)" % name)
                elif _entry_problem(servers[name]):
                    problems.append("Cursor: MCP server '%s' is broken: %s" % (name, _entry_problem(servers[name])))

    if (home / ".codex").exists():
        servers = _codex_servers(codex_file) if codex_file.exists() else {}
        if servers is None:
            problems.append("Codex: cannot parse config.toml, so required MCP servers are unverified")
        else:
            for name in required:
                if name not in servers:
                    problems.append("Codex: MCP server '%s' is not registered (~/.codex/config.toml)" % name)
                elif _entry_problem(servers[name]):
                    problems.append("Codex: MCP server '%s' is broken: %s" % (name, _entry_problem(servers[name])))

    return problems
