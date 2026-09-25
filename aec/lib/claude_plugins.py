"""Claude Code's own plugin manager, as the source of truth for marketplace plugins.

AEC's catalog pins a version for each plugin, but Claude Code installs and
updates marketplace plugins itself, so the catalog version goes stale the day
upstream ships. These helpers ask Claude Code instead:

- ``installed_versions()``  -> ``claude plugin list --json``
- ``refresh_marketplace()`` -> ``claude plugin marketplace update <name>``
- ``update_plugin()``       -> ``claude plugin update <id> --json``

Claude Code has no check-only command: ``update`` is how you find out, and it
is a no-op (``updateOutcome: up_to_date``) when nothing newer exists. Skills,
rules and hooks have no Claude Code manager; AEC keeps handling those.
"""
from __future__ import annotations

import json
import subprocess
from typing import Dict, List, Optional

_TIMEOUT = 120


def _run(cmd: List[str]) -> Optional[subprocess.CompletedProcess]:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None


def _last_json_line(text: str) -> Optional[dict]:
    for line in reversed(text.strip().splitlines()):
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def is_claude_managed(record: dict) -> bool:
    """True when AEC recorded this plugin as a Claude Code marketplace install."""
    return record.get("install_type") == "marketplace"


def marketplace_of(plugin_id: str) -> str:
    """``ponytail@ponytail`` -> ``ponytail``."""
    return plugin_id.rpartition("@")[2]


def installed_versions() -> Dict[str, str]:
    """``{plugin_id: version}`` for every plugin Claude Code has installed."""
    result = _run(["claude", "plugin", "list", "--json"])
    if result is None or result.returncode != 0:
        return {}
    try:
        entries = json.loads(result.stdout)
    except ValueError:
        return {}
    if isinstance(entries, dict):  # --available shape
        entries = entries.get("installed", [])
    return {e["id"]: e.get("version", "") for e in entries if isinstance(e, dict) and "id" in e}


def commands_blocked(pref) -> Optional[str]:
    """Why AEC must not run ``claude plugin`` commands, or None when it may.

    Shared by ``aec update`` and ``aec upgrade`` so both honor the same
    guarantee: nothing runs without ``claude`` or under ``instructions-only``.
    """
    from .config import detect_agents
    from .plugin_install import effective_policy

    if "claude" not in detect_agents():
        return "claude is not installed"
    if effective_policy("marketplace", has_run=True, pref=pref) != "run":
        return "plugins.execution is instructions-only"
    return None


def installed_record(manifest_def: dict, result: dict) -> tuple:
    """``(version, plugin_id)`` to record after ``install_plugin`` ran.

    For a marketplace plugin that was actually installed, the version is what
    Claude Code reports (the catalog's pin is only a fallback) and the plugin
    id is kept so upgrades can ask Claude Code about it directly.
    """
    version = manifest_def.get("version", "0.0.0")
    if result.get("install_type") != "marketplace":
        return version, ""
    plugin_id = manifest_def["install"]["plugin"]
    if result.get("executed"):
        version = installed_versions().get(plugin_id) or version
    return version, plugin_id


def refresh_marketplace(name: str) -> bool:
    """Pull a marketplace's catalog so ``update`` sees new releases."""
    result = _run(["claude", "plugin", "marketplace", "update", name])
    return result is not None and result.returncode == 0


def update_plugin(plugin_id: str) -> dict:
    """Run ``claude plugin update``; returns ``{ok, outcome, old, new, message}``.

    ``outcome`` is Claude Code's ``updateOutcome`` (``up_to_date`` when there
    was nothing to do). When ``ok`` is False, ``message`` carries Claude Code's
    own explanation (e.g. a marketplace-declared command that needs manual
    confirmation) so the caller can show it instead of a bare "failed".
    """
    result = _run(["claude", "plugin", "update", plugin_id, "--json"])
    if result is None:
        return {"ok": False, "outcome": "", "old": "", "new": "",
                "message": "could not run `claude` (missing or timed out)"}
    data = _last_json_line(result.stdout) or {}
    ok = result.returncode == 0 and data.get("outcome") == "ok"
    stderr_lines = (result.stderr or "").strip().splitlines()
    message = data.get("message") or (stderr_lines[-1] if stderr_lines else "")
    return {
        "ok": ok,
        "outcome": data.get("updateOutcome", ""),
        "old": data.get("oldVersion", ""),
        "new": data.get("newVersion", ""),
        "message": message,
    }
