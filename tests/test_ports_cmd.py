"""Tests for aec ports CLI commands."""

import json
from pathlib import Path

import pytest


def _make_registry(temp_dir: Path, ports: dict = None) -> Path:
    """Helper to create a registry file."""
    reg_path = temp_dir / "ports-registry.json"
    data = {"version": "1.0.0", "ports": ports or {}}
    reg_path.write_text(json.dumps(data))
    return reg_path


def _make_aec_json(project_dir: Path, project_name: str, ports: dict) -> Path:
    """Helper to create a .aec.json file."""
    project_dir.mkdir(parents=True, exist_ok=True)
    aec_json = project_dir / ".aec.json"
    aec_json.write_text(json.dumps({"project": project_name, "ports": ports}))
    return aec_json


class TestRunPortsList:
    """Test run_ports_list command."""

    def test_empty_registry(self, temp_dir, monkeypatch, capsys):
        """Should show info message when no ports registered."""
        reg_path = _make_registry(temp_dir)
        monkeypatch.setattr("aec.commands.ports.AEC_PORTS_REGISTRY", reg_path)

        from aec.commands.ports import run_ports_list

        run_ports_list()
        output = capsys.readouterr().out
        assert "No ports registered" in output

    def test_populated_registry(self, temp_dir, monkeypatch, capsys):
        """Should display ports grouped by project."""
        reg_path = _make_registry(temp_dir, {
            "3000": {
                "project": "web-app",
                "project_path": "/tmp/web-app",
                "key": "dev_server",
                "protocol": "http",
                "description": "Dev server",
                "registered_at": "2026-01-01T00:00:00Z",
            },
            "5432": {
                "project": "web-app",
                "project_path": "/tmp/web-app",
                "key": "postgres",
                "protocol": "",
                "description": "Database",
                "registered_at": "2026-01-01T00:00:00Z",
            },
        })
        monkeypatch.setattr("aec.commands.ports.AEC_PORTS_REGISTRY", reg_path)

        from aec.commands.ports import run_ports_list

        run_ports_list()
        output = capsys.readouterr().out
        assert "web-app" in output
        assert "3000" in output
        assert "5432" in output
        assert "dev_server" in output
        assert "2 port(s)" in output


class TestRunPortsCheck:
    """Test run_ports_check command."""

    def test_no_conflicts(self, temp_dir, monkeypatch, capsys):
        """Should report no conflicts when ports are free."""
        reg_path = _make_registry(temp_dir)
        monkeypatch.setattr("aec.commands.ports.AEC_PORTS_REGISTRY", reg_path)

        project = temp_dir / "my-project"
        _make_aec_json(project, "my-project", {"dev": {"port": 3000}})

        from aec.commands.ports import run_ports_check

        run_ports_check(str(project))
        output = capsys.readouterr().out
        assert "No conflicts" in output

    def test_with_conflicts(self, temp_dir, monkeypatch, capsys):
        """Should report conflicts when ports are taken."""
        reg_path = _make_registry(temp_dir, {
            "3000": {
                "project": "other-app",
                "project_path": "/tmp/other-app",
                "key": "web",
                "protocol": "",
                "description": "",
                "registered_at": "2026-01-01T00:00:00Z",
            },
        })
        monkeypatch.setattr("aec.commands.ports.AEC_PORTS_REGISTRY", reg_path)

        project = temp_dir / "my-project"
        _make_aec_json(project, "my-project", {"dev": {"port": 3000}})

        from aec.commands.ports import run_ports_check

        run_ports_check(str(project))
        output = capsys.readouterr().out
        assert "1 conflict" in output
        assert "other-app" in output

    def test_missing_aec_json(self, temp_dir, monkeypatch, capsys):
        """Should report error when .aec.json is missing."""
        reg_path = _make_registry(temp_dir)
        monkeypatch.setattr("aec.commands.ports.AEC_PORTS_REGISTRY", reg_path)

        project = temp_dir / "no-config"
        project.mkdir()

        from aec.commands.ports import run_ports_check

        run_ports_check(str(project))
        output = capsys.readouterr().out
        assert "No .aec.json" in output


class TestRunPortsRegister:
    """Test run_ports_register command."""

    def test_register_from_aec_json(self, temp_dir, monkeypatch, capsys):
        """Should register ports from .aec.json and save to registry."""
        reg_path = _make_registry(temp_dir)
        monkeypatch.setattr("aec.commands.ports.AEC_PORTS_REGISTRY", reg_path)

        project = temp_dir / "my-project"
        _make_aec_json(project, "my-project", {
            "dev_server": {"port": 3000, "protocol": "http", "description": "Dev"},
            "api": {"port": 3001, "protocol": "http"},
        })

        from aec.commands.ports import run_ports_register

        run_ports_register(str(project))
        output = capsys.readouterr().out
        assert "Registered port 3000" in output
        assert "Registered port 3001" in output
        assert "2 port(s)" in output

        # Verify persisted
        saved = json.loads(reg_path.read_text())
        assert "3000" in saved["ports"]
        assert "3001" in saved["ports"]

    def test_register_skips_conflicts(self, temp_dir, monkeypatch, capsys):
        """Should skip ports that conflict with existing registrations."""
        reg_path = _make_registry(temp_dir, {
            "3000": {
                "project": "existing",
                "project_path": "/tmp/existing",
                "key": "web",
                "protocol": "",
                "description": "",
                "registered_at": "2026-01-01T00:00:00Z",
            },
        })
        monkeypatch.setattr("aec.commands.ports.AEC_PORTS_REGISTRY", reg_path)

        project = temp_dir / "new-project"
        _make_aec_json(project, "new-project", {
            "web": {"port": 3000},
            "api": {"port": 3001},
        })

        from aec.commands.ports import run_ports_register

        run_ports_register(str(project))
        output = capsys.readouterr().out
        assert "already registered" in output
        assert "1 port(s)" in output


class TestRunPortsUnregister:
    """Test run_ports_unregister command."""

    def test_unregister_project(self, temp_dir, monkeypatch, capsys):
        """Should remove all ports for a project and save."""
        project_path = str((temp_dir / "my-project").resolve())
        reg_path = _make_registry(temp_dir, {
            "3000": {
                "project": "my-project",
                "project_path": project_path,
                "key": "web",
                "protocol": "",
                "description": "",
                "registered_at": "2026-01-01T00:00:00Z",
            },
        })
        monkeypatch.setattr("aec.commands.ports.AEC_PORTS_REGISTRY", reg_path)

        from aec.commands.ports import run_ports_unregister

        run_ports_unregister(project_path)
        output = capsys.readouterr().out
        assert "Freed 1 port(s)" in output

        saved = json.loads(reg_path.read_text())
        assert saved["ports"] == {}

    def test_unregister_no_ports(self, temp_dir, monkeypatch, capsys):
        """Should show info when no ports found for project."""
        reg_path = _make_registry(temp_dir)
        monkeypatch.setattr("aec.commands.ports.AEC_PORTS_REGISTRY", reg_path)

        from aec.commands.ports import run_ports_unregister

        run_ports_unregister("/tmp/nonexistent")
        output = capsys.readouterr().out
        assert "No ports registered" in output
