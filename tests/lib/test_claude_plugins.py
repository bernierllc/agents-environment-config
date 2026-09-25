"""aec.lib.claude_plugins: parse Claude Code's plugin manager output."""

import json
import subprocess

import pytest
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
    assert result == {"ok": True, "outcome": "up_to_date", "old": "6.4.1", "new": "6.4.1",
                      "message": UPDATE_UP_TO_DATE["message"]}


def test_update_failure_keeps_claudes_message():
    refusal = {"command": "update", "outcome": "error",
               "message": "marketplace-declared command must be confirmed; pass -y"}
    with patch("subprocess.run", return_value=_proc(json.dumps(refusal), 0)):
        result = cp.update_plugin("x@y")
    assert not result["ok"] and "must be confirmed" in result["message"]
    with patch("subprocess.run", return_value=MagicMock(stdout="", returncode=1, stderr="boom\nfatal: no net")):
        assert cp.update_plugin("x@y")["message"] == "fatal: no net"


def test_update_cannot_run():
    for err in (FileNotFoundError("claude"), subprocess.TimeoutExpired("claude", 120)):
        with patch("subprocess.run", side_effect=err):
            result = cp.update_plugin("x@y")
        assert not result["ok"] and result["message"]


def test_installed_record():
    mkt = {"version": "1.0.0", "install_type": "marketplace", "install": {"plugin": "p@m"}}
    with patch.object(cp, "installed_versions", return_value={"p@m": "1.4.0"}):
        assert cp.installed_record(mkt, {"install_type": "marketplace", "executed": True}) == ("1.4.0", "p@m")
        assert cp.installed_record(mkt, {"install_type": "marketplace", "executed": False}) == ("1.0.0", "p@m")
    ext = {"version": "2.0.0", "install_type": "external"}
    assert cp.installed_record(ext, {"install_type": "external"}) == ("2.0.0", "")


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
         patch("aec.lib.preferences.get_setting", return_value=None), \
         patch("aec.commands.update.refresh_marketplace", return_value=True) as refresh:
        assert _refresh_claude_plugins(manifest, ["global"]) == 1
    refresh.assert_called_once_with("ponytail")


@pytest.mark.parametrize("agents,pref,reason", [
    ({}, None, "not installed"),
    ({"claude": {}}, "instructions-only", "instructions-only"),
])
def test_aec_update_skips_refresh_when_blocked(capsys, agents, pref, reason):
    from aec.commands.update import _refresh_claude_plugins

    manifest = {"global": {"plugins": {
        "ponytail": {"install_type": "marketplace", "pluginId": "ponytail@ponytail"}}}, "repos": {}}
    with patch("aec.lib.config.detect_agents", return_value=agents), \
         patch("aec.lib.preferences.get_setting", return_value=pref), \
         patch("aec.commands.update.refresh_marketplace") as refresh:
        assert _refresh_claude_plugins(manifest, ["global"]) == 1
    refresh.assert_not_called()
    assert reason in capsys.readouterr().out


def test_aec_apply_records_claude_version_and_id(tmp_path):
    """aec apply is the second plugin-install writer; it records like install does."""
    from aec.commands import apply_cmd
    from aec.lib.manifest_v2 import load_manifest

    catalog = tmp_path / "plugins" / "mkt"
    catalog.mkdir(parents=True)
    (catalog / "plugin.json").write_text(json.dumps({
        "schema": "loadout/v1", "item_type": "plugin", "name": "mkt", "version": "1.0.0",
        "description": "d", "source": "https://example.test", "install_type": "marketplace",
        "install": {"marketplace": "owner/mkt", "plugin": "mkt@mkt"},
    }))
    manifest_path = tmp_path / "installed.json"

    def fake_run(cmd, *a, **k):
        out = json.dumps([{"id": "mkt@mkt", "version": "1.4.2"}]) if cmd[:3] == ["claude", "plugin", "list"] else ""
        return _proc(out)

    with patch.object(apply_cmd, "_manifest_path", return_value=manifest_path), \
         patch("aec.lib.config.detect_agents", return_value={"claude": {}}), \
         patch("subprocess.run", side_effect=fake_run):
        apply_cmd._apply_plugins([("global", "mkt")], source_dirs={"plugins": tmp_path / "plugins"}, yes=True)

    entry = load_manifest(manifest_path)["global"]["plugins"]["mkt"]
    assert entry["version"] == "1.4.2" and entry["pluginId"] == "mkt@mkt"


def test_aec_update_never_calls_a_scope_with_managed_plugins_up_to_date(capsys):
    """Codex P2 on #87: the per-scope summary must not say "(up to date)" for an unchecked plugin."""
    from pathlib import Path
    from aec.commands.update import _report_scope_outdated

    manifest = {"global": {"plugins": {"p": {"install_type": "marketplace", "version": "1.0.0"}}}, "repos": {}}
    assert _report_scope_outdated(manifest, "global", {"plugins": Path(__file__).parent}) == 1
    assert "managed by Claude Code" in capsys.readouterr().out



def test_aec_update_summary_counts_managed_plugins_in_other_repos(tmp_path, capsys):
    """Codex P2 on #87: a Claude-managed plugin only in another repo rules out "Everything is up to date"."""
    from aec.commands import update

    other = tmp_path / "other"
    other.mkdir()
    manifest = {"global": {}, "repos": {str(other): {
        "plugins": {"p": {"install_type": "marketplace", "pluginId": "p@m", "version": "1.0.0"}}}}}
    with patch.object(update, "get_repo_root", return_value=tmp_path), \
         patch.object(update, "fetch_latest", return_value=True), \
         patch.object(update, "load_manifest", return_value=manifest), \
         patch.object(update, "save_manifest"), \
         patch.object(update, "get_source_dirs", return_value={}), \
         patch.object(update, "find_tracked_repo", return_value=None), \
         patch.object(update, "get_all_tracked_repos", return_value=[other]), \
         patch.object(update, "refresh_marketplace", return_value=True), \
         patch.object(update, "_refresh_org_configs"), \
         patch.object(update, "check_blurb_drift"), \
         patch("aec.lib.config.detect_agents", return_value={"claude": {}}), \
         patch("aec.lib.preferences.get_setting", return_value=None):
        update.run_update()
    out = capsys.readouterr().out
    assert "Everything is up to date" not in out
    assert "Run `aec upgrade` to apply." in out
