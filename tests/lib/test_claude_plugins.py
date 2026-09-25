"""aec.lib.claude_plugins: parse Claude Code's plugin manager output."""

import json
import subprocess
from unittest.mock import MagicMock, patch

from aec.lib import claude_plugins as cp

# Shapes copied from real `claude plugin ... --json` output (Claude Code, 2026-09-25).
UPDATE_UP_TO_DATE = {
    "command": "update", "outcome": "ok", "plugin": "superpowers@claude-plugins-official",
    "pluginId": "superpowers@claude-plugins-official", "scope": "user",
    "message": "superpowers is already at the latest version (6.4.1).",
    "updateOutcome": "up_to_date", "oldVersion": "6.4.1", "newVersion": "6.4.1",
}
LIST = [{"id": "ponytail@ponytail", "version": "4.10.0", "scope": "user", "enabled": True}]


def _proc(stdout="", returncode=0):
    return MagicMock(stdout=stdout, returncode=returncode, stderr="")


def test_update_parses_last_json_line():
    out = "Checking...\n" + json.dumps(UPDATE_UP_TO_DATE) + "\n"
    with patch("subprocess.run", return_value=_proc(out)) as run:
        result = cp.update_plugin("superpowers@claude-plugins-official")
    assert run.call_args[0][0] == ["claude", "plugin", "update", "superpowers@claude-plugins-official", "--json"]
    assert result == {"outcome": "up_to_date", "old": "6.4.1", "new": "6.4.1",
                      "message": UPDATE_UP_TO_DATE["message"]}


def test_update_failure_returns_none():
    with patch("subprocess.run", return_value=_proc(json.dumps({"outcome": "error"}), 1)):
        assert cp.update_plugin("x@y") is None
    with patch("subprocess.run", side_effect=FileNotFoundError("claude")):
        assert cp.update_plugin("x@y") is None
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 120)):
        assert cp.update_plugin("x@y") is None


def test_installed_versions():
    with patch("subprocess.run", return_value=_proc(json.dumps(LIST))):
        assert cp.installed_versions() == {"ponytail@ponytail": "4.10.0"}
    with patch("subprocess.run", return_value=_proc(json.dumps({"installed": LIST, "available": []}))):
        assert cp.installed_versions() == {"ponytail@ponytail": "4.10.0"}
    with patch("subprocess.run", return_value=_proc("not json")):
        assert cp.installed_versions() == {}


def test_marketplace_of_and_managed():
    assert cp.marketplace_of("superpowers@claude-plugins-official") == "claude-plugins-official"
    assert cp.is_claude_managed({"install_type": "marketplace"})
    assert not cp.is_claude_managed({"install_type": "per-tool"})


def test_aec_update_refreshes_marketplaces_of_managed_plugins():
    from aec.commands.update import _refresh_claude_plugins

    manifest = {"global": {"plugins": {
        "ponytail": {"install_type": "marketplace", "pluginId": "ponytail@ponytail", "version": "4.10.0"},
        "old": {"install_type": "per-tool", "version": "1.0.0"},
    }}, "repos": {}}
    with patch("aec.lib.config.detect_agents", return_value={"claude": {}}), \
         patch("aec.commands.update.refresh_marketplace", return_value=True) as refresh:
        assert _refresh_claude_plugins(manifest, ["global"]) == 1
    refresh.assert_called_once_with("ponytail")
