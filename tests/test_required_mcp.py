"""aec doctor must fail loudly when a required MCP server is missing from an installed agent client.

Real config files in a temp home; the only patch is the preferences file location.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from aec.lib.required_mcp import check_required_mcp_servers, required_servers


def _exe(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _claude(home: Path, servers: dict) -> None:
    (home / ".claude").mkdir(exist_ok=True)
    (home / ".claude.json").write_text(json.dumps({"mcpServers": servers}))


def _cursor(home: Path, servers: dict) -> None:
    (home / ".cursor").mkdir(exist_ok=True)
    (home / ".cursor" / "mcp.json").write_text(json.dumps({"mcpServers": servers}))


def _codex(home: Path, body: str) -> None:
    (home / ".codex").mkdir(exist_ok=True)
    (home / ".codex" / "config.toml").write_text(body)


def test_required_servers_normalises_and_rejects_malformed() -> None:
    assert required_servers(None) == []
    assert required_servers([" my-server ", "my-server", "other"]) == ["my-server", "other"]
    for bad in ("my-server", ["my-server", 3], ["my-server", ""], {"a": 1}):
        with pytest.raises(ValueError):
            required_servers(bad)


def test_no_clients_installed_means_nothing_to_check(tmp_path: Path) -> None:
    assert check_required_mcp_servers(["my-server"], tmp_path) == []


def test_every_client_registered_passes(tmp_path: Path) -> None:
    exe = _exe(tmp_path / "bin" / "my-server-mcp")
    entry = {"type": "stdio", "command": str(exe)}
    _claude(tmp_path, {"my-server": entry})
    _cursor(tmp_path, {"my-server": entry})
    _codex(tmp_path, f'[mcp_servers.my-server]\ncommand = "{exe}"\nstartup_timeout_sec = 60.0\n')
    assert check_required_mcp_servers(["my-server"], tmp_path) == []


def test_missing_in_each_client_is_reported_per_client(tmp_path: Path) -> None:
    _claude(tmp_path, {"other": {"command": "/bin/sh"}})
    _cursor(tmp_path, {})
    _codex(tmp_path, '[mcp_servers.other]\ncommand = "/bin/sh"\n')
    problems = check_required_mcp_servers(["my-server"], tmp_path)
    assert [p.split(":")[0] for p in problems] == ["Claude Code", "Cursor", "Codex"]
    assert all("my-server" in p and "not registered" in p for p in problems)


def test_codex_prefix_name_is_not_a_match(tmp_path: Path) -> None:
    # [mcp_servers.my-server-extra] must not satisfy a requirement for my-server
    _codex(tmp_path, '[mcp_servers.my-server-extra]\ncommand = "/bin/sh"\n')
    assert any("Codex" in p for p in check_required_mcp_servers(["my-server"], tmp_path))


def test_codex_entry_is_read_only_from_its_own_table(tmp_path: Path) -> None:
    # the next table's command must not leak into the required server's entry
    _codex(tmp_path, '[mcp_servers.my-server]\nstartup_timeout_sec = 60.0\n\n[mcp_servers.other]\ncommand = "/bin/sh"\n')
    problems = check_required_mcp_servers(["my-server"], tmp_path)
    assert len(problems) == 1 and "neither command nor url" in problems[0]


@pytest.mark.parametrize(
    "toml",
    [
        '[mcp_servers.my-server] # note\ncommand = "/bin/sh"\n',
        "[mcp_servers.my-server]\ncommand = '/bin/sh'\n",
        "[mcp_servers.'my-server']\ncommand = \"/bin/sh\"\n",
        '[mcp_servers.my-server]\nargs = [\n  ["x"],\n]\ncommand = "/bin/sh"\n',
        '[mcp_servers.my-server]\ncommand = "/bin/sh"\n[mcp_servers.my-server.env]\nKEY = "v"\n',
    ],
)
def test_valid_codex_toml_variants_pass(tmp_path: Path, toml: str) -> None:
    _codex(tmp_path, toml)
    assert check_required_mcp_servers(["my-server"], tmp_path) == []


def test_unparseable_codex_toml_is_unverified(tmp_path: Path) -> None:
    _codex(tmp_path, "[mcp_servers.my-server\ncommand = ")
    (problem,) = check_required_mcp_servers(["my-server"], tmp_path)
    assert "unverified" in problem


def test_non_utf8_codex_toml_is_unverified_not_a_crash(tmp_path: Path) -> None:
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_bytes(b"\xff\xfe[x]")
    (problem,) = check_required_mcp_servers(["my-server"], tmp_path)
    assert "unverified" in problem


def test_disabled_server_is_not_registered_for_use(tmp_path: Path) -> None:
    _codex(tmp_path, '[mcp_servers.my-server]\ncommand = "/bin/sh"\nenabled = false\n')
    _cursor(tmp_path, {"my-server": {"command": "/bin/sh", "disabled": True}})
    problems = check_required_mcp_servers(["my-server"], tmp_path)
    assert len(problems) == 2 and all("disabled" in p for p in problems)


def test_command_that_is_a_directory_is_broken(tmp_path: Path) -> None:
    _claude(tmp_path, {"my-server": {"command": str(tmp_path)}})
    (problem,) = check_required_mcp_servers(["my-server"], tmp_path)
    assert "does not exist" in problem


def test_stdio_command_that_does_not_exist_is_broken(tmp_path: Path) -> None:
    _claude(tmp_path, {"my-server": {"command": str(tmp_path / "gone")}})
    (problem,) = check_required_mcp_servers(["my-server"], tmp_path)
    assert "broken" in problem and "does not exist" in problem


def test_stdio_command_that_is_not_executable_is_broken(tmp_path: Path) -> None:
    f = tmp_path / "bin" / "x"
    f.parent.mkdir()
    f.write_text("x")
    f.chmod(0o644)
    _claude(tmp_path, {"my-server": {"command": str(f)}})
    (problem,) = check_required_mcp_servers(["my-server"], tmp_path)
    assert "not executable" in problem


def test_url_entry_needs_no_local_binary(tmp_path: Path) -> None:
    _cursor(tmp_path, {"my-server": {"url": "https://example.com/mcp"}})
    assert check_required_mcp_servers(["my-server"], tmp_path) == []


def test_unreadable_claude_json_is_unverified_not_passing(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude.json").write_text("{not json")
    (problem,) = check_required_mcp_servers(["my-server"], tmp_path)
    assert "unverified" in problem


def test_server_in_claude_settings_json_counts(tmp_path: Path) -> None:
    # aec's own installer writes mcpServers to ~/.claude/settings.json
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(
        json.dumps({"mcpServers": {"my-server": {"command": "/bin/sh"}}})
    )
    assert check_required_mcp_servers(["my-server"], tmp_path) == []


def test_doctor_lists_the_issue_and_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from aec.commands.doctor import _check_required_mcp_servers

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    prefs = tmp_path / "preferences.json"
    prefs.write_text(json.dumps({"settings": {"required_mcp_servers": ["my-server"]}}))
    _claude(tmp_path, {})
    with patch("aec.lib.preferences.AEC_PREFERENCES", prefs):
        issues = _check_required_mcp_servers()
    assert issues and "my-server" in issues[0]


def test_doctor_requires_nothing_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from aec.commands.doctor import _check_required_mcp_servers

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    with patch("aec.lib.preferences.AEC_PREFERENCES", tmp_path / "absent.json"):
        assert _check_required_mcp_servers() == []


def test_doctor_flags_a_malformed_setting_instead_of_passing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from aec.commands.doctor import _check_required_mcp_servers

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    prefs = tmp_path / "preferences.json"
    prefs.write_text(json.dumps({"settings": {"required_mcp_servers": "my-server"}}))
    with patch("aec.lib.preferences.AEC_PREFERENCES", prefs):
        (issue,) = _check_required_mcp_servers()
    assert "must be a list" in issue


def test_doctor_command_exits_nonzero_when_a_check_fails() -> None:
    from typer.testing import CliRunner

    from aec.cli import app

    with patch("aec.commands.doctor.run_doctor", return_value=(False, ["x"])):
        assert CliRunner().invoke(app, ["doctor"]).exit_code == 1
    with patch("aec.commands.doctor.run_doctor", return_value=(True, [])):
        assert CliRunner().invoke(app, ["doctor"]).exit_code == 0


def test_real_doctor_run_exits_1_for_a_missing_required_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from aec.cli import app

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    prefs = tmp_path / "preferences.json"
    prefs.write_text(json.dumps({"settings": {"required_mcp_servers": ["my-server"]}}))
    _claude(tmp_path, {})
    with patch("aec.lib.preferences.AEC_PREFERENCES", prefs):
        result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "my-server" in result.output
