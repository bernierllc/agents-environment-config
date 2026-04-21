"""Tests for MCP server install/uninstall: mcp_settings, sources, manifest, commands."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from aec.lib.mcp_settings import (
    get_settings_path,
    read_mcp_servers,
    write_mcp_server,
    remove_mcp_server,
)
from aec.lib.sources import _discover_available_mcps
from aec.lib.manifest_v2 import (
    _empty_manifest,
    record_mcp_install,
    get_installed,
    remove_install,
)
from aec.lib.installed_store import load_installed, record_item_install, remove_item_install
from aec.lib.scope import Scope


# ---------------------------------------------------------------------------
# mcp_settings.py
# ---------------------------------------------------------------------------

class TestGetSettingsPath:
    def test_global_scope(self, mock_home: Path) -> None:
        scope = Scope(is_global=True, repo_path=None)
        path = get_settings_path(scope)
        assert path == mock_home / ".claude" / "settings.json"

    def test_local_scope(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        scope = Scope(is_global=False, repo_path=repo)
        path = get_settings_path(scope)
        assert path == repo / ".claude" / "settings.json"


class TestReadMcpServers:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        result = read_mcp_servers(tmp_path / "settings.json")
        assert result == {}

    def test_no_mcp_servers_key_returns_empty(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({"hooks": {}}))
        assert read_mcp_servers(settings) == {}

    def test_returns_existing_entries(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({"mcpServers": {"foo": {"command": "foo"}}}))
        assert read_mcp_servers(settings) == {"foo": {"command": "foo"}}

    def test_corrupt_file_returns_empty(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        settings.write_text("not json{{")
        assert read_mcp_servers(settings) == {}


class TestWriteMcpServer:
    def test_creates_file_if_absent(self, tmp_path: Path) -> None:
        settings = tmp_path / ".claude" / "settings.json"
        write_mcp_server(settings, "jcodemunch", {"command": "jcodemunch-mcp"})
        data = json.loads(settings.read_text())
        assert data["mcpServers"]["jcodemunch"] == {"command": "jcodemunch-mcp"}

    def test_merges_into_existing_settings(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({"hooks": {"PostToolUse": []}, "mcpServers": {"other": {"command": "other"}}}))
        write_mcp_server(settings, "jcodemunch", {"command": "jcodemunch-mcp"})
        data = json.loads(settings.read_text())
        assert "hooks" in data
        assert data["mcpServers"]["other"] == {"command": "other"}
        assert data["mcpServers"]["jcodemunch"] == {"command": "jcodemunch-mcp"}

    def test_idempotent_overwrite(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        write_mcp_server(settings, "jcodemunch", {"command": "jcodemunch-mcp"})
        write_mcp_server(settings, "jcodemunch", {"command": "jcodemunch-mcp"})
        data = json.loads(settings.read_text())
        assert len(data["mcpServers"]) == 1

    def test_does_not_clobber_other_keys(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        original = {"permissions": {"allow": ["Bash"]}, "hooks": {}}
        settings.write_text(json.dumps(original))
        write_mcp_server(settings, "jcodemunch", {"command": "jcodemunch-mcp"})
        data = json.loads(settings.read_text())
        assert data["permissions"] == {"allow": ["Bash"]}
        assert data["hooks"] == {}


class TestRemoveMcpServer:
    def test_removes_existing_entry(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        write_mcp_server(settings, "jcodemunch", {"command": "jcodemunch-mcp"})
        result = remove_mcp_server(settings, "jcodemunch")
        assert result is True
        data = json.loads(settings.read_text())
        assert "mcpServers" not in data

    def test_returns_false_if_missing(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({"mcpServers": {}}))
        assert remove_mcp_server(settings, "nonexistent") is False

    def test_returns_false_if_file_absent(self, tmp_path: Path) -> None:
        assert remove_mcp_server(tmp_path / "settings.json", "anything") is False

    def test_preserves_other_mcp_servers(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({
            "mcpServers": {
                "jcodemunch": {"command": "jcodemunch-mcp"},
                "other": {"command": "other-mcp"},
            }
        }))
        remove_mcp_server(settings, "jcodemunch")
        data = json.loads(settings.read_text())
        assert "jcodemunch" not in data["mcpServers"]
        assert "other" in data["mcpServers"]

    def test_preserves_non_mcp_keys(self, tmp_path: Path) -> None:
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({
            "hooks": {"PostToolUse": []},
            "mcpServers": {"jcodemunch": {"command": "jcodemunch-mcp"}},
        }))
        remove_mcp_server(settings, "jcodemunch")
        data = json.loads(settings.read_text())
        assert "hooks" in data


# ---------------------------------------------------------------------------
# _discover_available_mcps (sources.py)
# ---------------------------------------------------------------------------

class TestDiscoverAvailableMcps:
    def test_empty_dir_returns_empty(self, tmp_path: Path) -> None:
        assert _discover_available_mcps(tmp_path) == {}

    def test_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        assert _discover_available_mcps(tmp_path / "nonexistent") == {}

    def test_discovers_valid_mcp(self, tmp_path: Path) -> None:
        mcp_dir = tmp_path / "jcodemunch"
        mcp_dir.mkdir()
        (mcp_dir / "mcp.json").write_text(json.dumps({
            "name": "jcodemunch",
            "description": "Code exploration",
            "version": "0.1.0",
            "install": {"pip": "jcodemunch-mcp"},
            "mcpServers": {"jcodemunch": {"command": "jcodemunch-mcp"}},
        }))
        result = _discover_available_mcps(tmp_path)
        assert "jcodemunch" in result
        assert result["jcodemunch"]["version"] == "0.1.0"
        assert result["jcodemunch"]["path"] == "jcodemunch"

    def test_skips_dirs_without_mcp_json(self, tmp_path: Path) -> None:
        (tmp_path / "no-def").mkdir()
        assert _discover_available_mcps(tmp_path) == {}

    def test_skips_missing_name_or_version(self, tmp_path: Path) -> None:
        mcp_dir = tmp_path / "incomplete"
        mcp_dir.mkdir()
        (mcp_dir / "mcp.json").write_text(json.dumps({"name": "incomplete"}))
        assert _discover_available_mcps(tmp_path) == {}

    def test_skips_corrupt_json(self, tmp_path: Path) -> None:
        mcp_dir = tmp_path / "bad"
        mcp_dir.mkdir()
        (mcp_dir / "mcp.json").write_text("not json")
        assert _discover_available_mcps(tmp_path) == {}

    def test_skips_hidden_dirs(self, tmp_path: Path) -> None:
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "mcp.json").write_text(json.dumps({"name": "hidden", "version": "1.0.0"}))
        assert _discover_available_mcps(tmp_path) == {}


# ---------------------------------------------------------------------------
# manifest_v2: record_mcp_install / get_installed / remove_install
# ---------------------------------------------------------------------------

class TestRecordMcpInstall:
    def test_records_in_global_section(self) -> None:
        manifest = _empty_manifest()
        record_mcp_install(manifest, "global", "jcodemunch", "0.1.0", "jcodemunch-mcp")
        entry = manifest["global"]["mcps"]["jcodemunch"]
        assert entry["version"] == "0.1.0"
        assert entry["package"] == "jcodemunch-mcp"
        assert "installedAt" in entry

    def test_records_in_repo_section(self, tmp_path: Path) -> None:
        manifest = _empty_manifest()
        repo_key = str(tmp_path)
        record_mcp_install(manifest, repo_key, "jcodemunch", "0.1.0", "jcodemunch-mcp")
        assert "jcodemunch" in manifest["repos"][repo_key]["mcps"]

    def test_get_installed_returns_mcp_entry(self) -> None:
        manifest = _empty_manifest()
        record_mcp_install(manifest, "global", "jcodemunch", "0.1.0", "jcodemunch-mcp")
        installed = get_installed(manifest, "global", "mcps")
        assert "jcodemunch" in installed

    def test_remove_install_clears_mcp_entry(self) -> None:
        manifest = _empty_manifest()
        record_mcp_install(manifest, "global", "jcodemunch", "0.1.0", "jcodemunch-mcp")
        remove_install(manifest, "global", "mcps", "jcodemunch")
        assert "jcodemunch" not in manifest["global"]["mcps"]


# ---------------------------------------------------------------------------
# installed_store: mcp type
# ---------------------------------------------------------------------------

class TestInstalledStoreMcp:
    def test_record_and_retrieve_mcp(self, mock_home: Path) -> None:
        record_item_install("mcp", "jcodemunch", "0.1.0")
        store = load_installed("mcp")
        assert "jcodemunch" in store["items"]
        assert store["items"]["jcodemunch"]["version"] == "0.1.0"

    def test_remove_mcp_install(self, mock_home: Path) -> None:
        record_item_install("mcp", "jcodemunch", "0.1.0")
        remove_item_install("mcp", "jcodemunch")
        store = load_installed("mcp")
        assert "jcodemunch" not in store["items"]


# ---------------------------------------------------------------------------
# _install_mcp integration (install_cmd.py)
# ---------------------------------------------------------------------------

class TestInstallMcp:
    def _make_mcp_source(self, repo: Path) -> Path:
        """Create a minimal mcp-servers/jcodemunch/mcp.json in the given repo."""
        mcp_dir = repo / "mcp-servers" / "jcodemunch"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "mcp.json").write_text(json.dumps({
            "name": "jcodemunch",
            "description": "Code exploration",
            "version": "0.1.0",
            "install": {"pip": "jcodemunch-mcp"},
            "mcpServers": {"jcodemunch": {"command": "jcodemunch-mcp"}},
        }))
        return repo

    def test_installs_mcp_server_globally(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = self._make_mcp_source(tmp_path / "aec-repo")
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: home)

        aec_home = home / ".agents-environment-config"
        aec_home.mkdir(parents=True)

        from aec.commands.install_cmd import _install_mcp
        from aec.lib import config as cfg

        monkeypatch.setattr(cfg, "get_repo_root", lambda: repo)
        monkeypatch.setattr("aec.commands.install_cmd.get_repo_root", lambda: repo)
        monkeypatch.setattr("aec.lib.sources.get_repo_root", lambda: repo)

        with patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            _install_mcp("jcodemunch", global_flag=True, yes=True)

        # pip install was called
        mock_run.assert_called_once_with(["pip", "install", "jcodemunch-mcp"])

        # settings.json written
        settings_path = home / ".claude" / "settings.json"
        assert settings_path.exists()
        data = json.loads(settings_path.read_text())
        assert data["mcpServers"]["jcodemunch"] == {"command": "jcodemunch-mcp"}

        # manifest recorded
        manifest_path = aec_home / "installed-manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert "jcodemunch" in manifest["global"]["mcps"]

    def test_unknown_mcp_exits_with_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = self._make_mcp_source(tmp_path / "aec-repo")
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: home)
        (home / ".agents-environment-config").mkdir(parents=True)

        from aec.commands.install_cmd import _install_mcp
        monkeypatch.setattr("aec.commands.install_cmd.get_repo_root", lambda: repo)
        monkeypatch.setattr("aec.lib.sources.get_repo_root", lambda: repo)

        with pytest.raises(SystemExit):
            _install_mcp("nonexistent", global_flag=True, yes=True)


# ---------------------------------------------------------------------------
# _uninstall_mcp integration (uninstall.py)
# ---------------------------------------------------------------------------

class TestUninstallMcp:
    def _write_installed_mcp(self, home: Path, settings_data: dict | None = None) -> None:
        aec_home = home / ".agents-environment-config"
        aec_home.mkdir(parents=True, exist_ok=True)

        from aec.lib.manifest_v2 import _empty_manifest, record_mcp_install, save_manifest
        manifest = _empty_manifest()
        record_mcp_install(manifest, "global", "jcodemunch", "0.1.0", "jcodemunch-mcp")
        save_manifest(manifest, aec_home / "installed-manifest.json")

        settings_path = home / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        if settings_data is None:
            settings_data = {"mcpServers": {"jcodemunch": {"command": "jcodemunch-mcp"}}}
        settings_path.write_text(json.dumps(settings_data))

    def test_removes_mcp_server_globally(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: home)
        self._write_installed_mcp(home)

        from aec.commands.uninstall import _uninstall_mcp

        with patch("subprocess.run"):
            _uninstall_mcp("jcodemunch", global_flag=True, yes=True)

        settings_path = home / ".claude" / "settings.json"
        data = json.loads(settings_path.read_text())
        assert "mcpServers" not in data

    def test_warns_if_not_in_manifest(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: home)
        (home / ".agents-environment-config").mkdir(parents=True)

        from aec.commands.uninstall import _uninstall_mcp

        _uninstall_mcp("nonexistent", global_flag=True, yes=True)
