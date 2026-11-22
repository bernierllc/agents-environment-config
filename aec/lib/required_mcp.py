"""Check that the MCP servers a user requires are registered in every installed agent client.

The required set is the ``required_mcp_servers`` list under preferences ``settings`` (empty by
default, so a first-time user sees no check). Each installed client is checked on its own config:

- Claude Code: ``mcpServers`` in ``~/.claude.json`` or ``~/.claude/settings.json``
- Cursor: ``mcpServers`` in ``~/.cursor/mcp.json``
- Codex: a ``[mcp_servers.<name>]`` table in ``~/.codex/config.toml``

A client counts as installed when its config directory or file exists. A server registered with a
``command`` (stdio) must point at an executable that exists; a ``url`` entry needs no local binary.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

REQUIRED_MCP_SETTING = "required_mcp_servers"


def required_servers(settings_value: Any) -> List[str]:
    """Normalise the preference value to a list of server names."""
    if not isinstance(settings_value, list):
        return []
    return [s for s in settings_value if isinstance(s, str) and s.strip()]


def _json_servers(path: Path) -> Optional[Dict[str, Any]]:
    """The mcpServers dict of a JSON config, or None when the file cannot be read (unverifiable)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    servers = data.get("mcpServers", {}) if isinstance(data, dict) else {}
    return servers if isinstance(servers, dict) else {}


def _toml_entry(path: Path, name: str) -> Optional[Dict[str, str]]:
    """Fields of ``[mcp_servers.<name>]`` in a Codex config.toml, None when the table is absent.

    Hand-rolled because Python 3.9 has no tomllib; only the table header and its ``command`` /
    ``url`` lines matter here.
    """
    text = path.read_text(encoding="utf-8")
    header = re.compile(r"^\[mcp_servers\.(?:%s|\"%s\")\]\s*$" % (re.escape(name), re.escape(name)))
    entry: Optional[Dict[str, str]] = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            if entry is not None:
                break
            if header.match(stripped):
                entry = {}
            continue
        if entry is not None:
            m = re.match(r'^(command|url)\s*=\s*"([^"]*)"', stripped)
            if m:
                entry[m.group(1)] = m.group(2)
    return entry


def _command_problem(command: str) -> Optional[str]:
    resolved = command if os.path.isabs(command) else shutil.which(command)
    if not resolved or not os.path.exists(resolved):
        return "command %s does not exist" % command
    if not os.access(resolved, os.X_OK):
        return "command %s is not executable" % command
    return None


def _entry_problem(entry: Any) -> Optional[str]:
    """Why a registered entry cannot work, or None when it looks usable."""
    if not isinstance(entry, dict):
        return "entry is not a table"
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
        for name in required:
            try:
                entry = _toml_entry(codex_file, name) if codex_file.exists() else None
            except OSError:
                problems.append("Codex: cannot read config.toml, so required MCP servers are unverified")
                break
            if entry is None:
                problems.append("Codex: MCP server '%s' is not registered (~/.codex/config.toml)" % name)
            elif entry.get("command"):
                why = _command_problem(entry["command"])
                if why:
                    problems.append("Codex: MCP server '%s' is broken: %s" % (name, why))
            elif not entry.get("url"):
                problems.append("Codex: MCP server '%s' is broken: entry has neither command nor url" % name)

    return problems
