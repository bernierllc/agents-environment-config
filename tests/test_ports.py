"""Tests for aec.lib.ports module — port registry CRUD operations."""

import json
from pathlib import Path

import pytest


class TestDefaultRegistryStructure:
    """Test that the default registry has the required structure."""

    def test_default_has_version_and_ports(self):
        """Default registry should have 'version' and 'ports' keys."""
        from aec.lib.ports import _default_registry

        reg = _default_registry()
        assert "version" in reg
        assert "ports" in reg
        assert reg["version"] == "1.0.0"
        assert reg["ports"] == {}


class TestLoadRegistry:
    """Test load_registry function."""

    def test_returns_default_when_file_missing(self, temp_dir):
        """Should return default structure when file does not exist."""
        from aec.lib.ports import load_registry

        result = load_registry(temp_dir / "nonexistent.json")
        assert result == {"version": "1.0.0", "ports": {}}

    def test_handles_corrupt_json(self, temp_dir):
        """Should return default structure if JSON is corrupt."""
        from aec.lib.ports import load_registry

        bad_file = temp_dir / "ports-registry.json"
        bad_file.write_text("{not valid json!!!")

        result = load_registry(bad_file)
        assert result == {"version": "1.0.0", "ports": {}}

    def test_handles_invalid_structure(self, temp_dir):
        """Should return default if file lacks required keys."""
        from aec.lib.ports import load_registry

        bad_file = temp_dir / "ports-registry.json"
        bad_file.write_text(json.dumps({"something": "else"}))

        result = load_registry(bad_file)
        assert result == {"version": "1.0.0", "ports": {}}

    def test_loads_valid_registry(self, temp_dir):
        """Should load and return a valid registry file."""
        from aec.lib.ports import load_registry

        reg_file = temp_dir / "ports-registry.json"
        data = {
            "version": "1.0.0",
            "ports": {
                "3000": {
                    "project": "my-app",
                    "project_path": "/tmp/my-app",
                    "key": "dev",
                    "protocol": "http",
                    "description": "Dev server",
                    "registered_at": "2026-01-01T00:00:00Z",
                }
            },
        }
        reg_file.write_text(json.dumps(data))

        result = load_registry(reg_file)
        assert result["ports"]["3000"]["project"] == "my-app"


class TestSaveRegistry:
    """Test save_registry function."""

    def test_creates_file_and_parent_dirs(self, temp_dir):
        """Should create parent dirs and write registry to disk."""
        from aec.lib.ports import save_registry

        reg_file = temp_dir / "sub" / "dir" / "ports-registry.json"
        data = {"version": "1.0.0", "ports": {}}

        save_registry(data, reg_file)

        assert reg_file.exists()
        loaded = json.loads(reg_file.read_text())
        assert loaded == data

    def test_save_load_round_trip(self, temp_dir):
        """Save followed by load should return the same data."""
        from aec.lib.ports import save_registry, load_registry

        reg_file = temp_dir / "ports-registry.json"
        data = {
            "version": "1.0.0",
            "ports": {
                "8080": {
                    "project": "api",
                    "project_path": "/tmp/api",
                    "key": "server",
                    "protocol": "http",
                    "description": "API server",
                    "registered_at": "2026-04-01T12:00:00Z",
                }
            },
        }

        save_registry(data, reg_file)
        loaded = load_registry(reg_file)
        assert loaded == data


class TestRegisterPort:
    """Test register_port function."""

    def test_register_new_port(self):
        """Should register a new port and return 'registered'."""
        from aec.lib.ports import register_port

        registry = {"version": "1.0.0", "ports": {}}
        result = register_port(
            registry,
            port=3000,
            project="my-app",
            project_path="/tmp/my-app",
            key="dev_server",
            protocol="http",
            description="Development server",
        )

        assert result == "registered"
        assert "3000" in registry["ports"]
        entry = registry["ports"]["3000"]
        assert entry["project"] == "my-app"
        assert entry["project_path"] == "/tmp/my-app"
        assert entry["key"] == "dev_server"
        assert entry["protocol"] == "http"
        assert entry["description"] == "Development server"
        assert "registered_at" in entry

    def test_conflict_on_existing_port(self):
        """Should return 'conflict' for already-registered port (first-come-first-served)."""
        from aec.lib.ports import register_port

        registry = {
            "version": "1.0.0",
            "ports": {
                "3000": {
                    "project": "first-app",
                    "project_path": "/tmp/first-app",
                    "key": "dev",
                    "protocol": "",
                    "description": "",
                    "registered_at": "2026-01-01T00:00:00Z",
                }
            },
        }
        result = register_port(
            registry,
            port=3000,
            project="second-app",
            project_path="/tmp/second-app",
            key="dev",
        )

        assert result == "conflict"
        # Original registration should be unchanged
        assert registry["ports"]["3000"]["project"] == "first-app"

    def test_register_port_includes_timestamp(self):
        """Registered entry should include an ISO UTC timestamp."""
        from aec.lib.ports import register_port

        registry = {"version": "1.0.0", "ports": {}}
        register_port(registry, port=5000, project="p", project_path="/p", key="k")

        ts = registry["ports"]["5000"]["registered_at"]
        assert ts.endswith("Z")
        assert "T" in ts


class TestUnregisterProjectPorts:
    """Test unregister_project_ports function."""

    def test_removes_all_ports_for_project(self):
        """Should remove all ports belonging to a project path."""
        from aec.lib.ports import unregister_project_ports

        registry = {
            "version": "1.0.0",
            "ports": {
                "3000": {
                    "project": "my-app",
                    "project_path": "/tmp/my-app",
                    "key": "web",
                    "protocol": "",
                    "description": "",
                    "registered_at": "2026-01-01T00:00:00Z",
                },
                "3001": {
                    "project": "my-app",
                    "project_path": "/tmp/my-app",
                    "key": "api",
                    "protocol": "",
                    "description": "",
                    "registered_at": "2026-01-01T00:00:00Z",
                },
                "4000": {
                    "project": "other-app",
                    "project_path": "/tmp/other-app",
                    "key": "web",
                    "protocol": "",
                    "description": "",
                    "registered_at": "2026-01-01T00:00:00Z",
                },
            },
        }

        freed = unregister_project_ports(registry, "/tmp/my-app")

        assert sorted(freed) == [3000, 3001]
        assert "3000" not in registry["ports"]
        assert "3001" not in registry["ports"]
        assert "4000" in registry["ports"]

    def test_returns_empty_when_no_ports(self):
        """Should return empty list when no ports match."""
        from aec.lib.ports import unregister_project_ports

        registry = {"version": "1.0.0", "ports": {}}
        freed = unregister_project_ports(registry, "/tmp/nonexistent")
        assert freed == []


class TestCheckConflicts:
    """Test check_conflicts function."""

    def test_detects_conflicts(self):
        """Should detect ports registered to other projects."""
        from aec.lib.ports import check_conflicts

        registry = {
            "version": "1.0.0",
            "ports": {
                "3000": {
                    "project": "other-app",
                    "project_path": "/tmp/other-app",
                    "key": "web",
                    "protocol": "",
                    "description": "",
                    "registered_at": "2026-01-01T00:00:00Z",
                },
            },
        }
        ports = {"dev_server": {"port": 3000}}

        conflicts = check_conflicts(registry, ports, "/tmp/my-app")

        assert len(conflicts) == 1
        assert conflicts[0]["port"] == 3000
        assert conflicts[0]["key"] == "dev_server"
        assert conflicts[0]["existing_project"] == "other-app"

    def test_no_conflicts_when_empty_registry(self):
        """Should return empty list when registry has no entries."""
        from aec.lib.ports import check_conflicts

        registry = {"version": "1.0.0", "ports": {}}
        ports = {"dev_server": {"port": 3000}}

        conflicts = check_conflicts(registry, ports, "/tmp/my-app")
        assert conflicts == []

    def test_own_ports_are_not_conflicts(self):
        """Ports registered by the same project_path should not conflict."""
        from aec.lib.ports import check_conflicts

        registry = {
            "version": "1.0.0",
            "ports": {
                "3000": {
                    "project": "my-app",
                    "project_path": "/tmp/my-app",
                    "key": "web",
                    "protocol": "",
                    "description": "",
                    "registered_at": "2026-01-01T00:00:00Z",
                },
            },
        }
        ports = {"dev_server": {"port": 3000}}

        conflicts = check_conflicts(registry, ports, "/tmp/my-app")
        assert conflicts == []

    def test_skips_entries_without_port_key(self):
        """Should skip port specs that lack a 'port' key."""
        from aec.lib.ports import check_conflicts

        registry = {"version": "1.0.0", "ports": {}}
        ports = {"no_port": {"protocol": "http"}}

        conflicts = check_conflicts(registry, ports, "/tmp/my-app")
        assert conflicts == []


class TestValidateRegistry:
    """Test validate_registry function."""

    def test_detects_stale_entries(self, temp_dir):
        """Should return entries whose project_path no longer exists."""
        from aec.lib.ports import validate_registry

        registry = {
            "version": "1.0.0",
            "ports": {
                "3000": {
                    "project": "dead-project",
                    "project_path": str(temp_dir / "does-not-exist"),
                    "key": "web",
                    "protocol": "",
                    "description": "",
                    "registered_at": "2026-01-01T00:00:00Z",
                },
                "4000": {
                    "project": "alive-project",
                    "project_path": str(temp_dir),
                    "key": "api",
                    "protocol": "",
                    "description": "",
                    "registered_at": "2026-01-01T00:00:00Z",
                },
            },
        }

        stale = validate_registry(registry)
        assert len(stale) == 1
        assert stale[0]["port"] == 3000
        assert stale[0]["project"] == "dead-project"

    def test_no_stale_when_all_valid(self, temp_dir):
        """Should return empty list when all paths exist."""
        from aec.lib.ports import validate_registry

        registry = {
            "version": "1.0.0",
            "ports": {
                "3000": {
                    "project": "good-project",
                    "project_path": str(temp_dir),
                    "key": "web",
                    "protocol": "",
                    "description": "",
                    "registered_at": "2026-01-01T00:00:00Z",
                },
            },
        }

        stale = validate_registry(registry)
        assert stale == []


class TestListPortsByProject:
    """Test list_ports_by_project function."""

    def test_groups_by_project(self):
        """Should group ports by project name."""
        from aec.lib.ports import list_ports_by_project

        registry = {
            "version": "1.0.0",
            "ports": {
                "3000": {
                    "project": "app-a",
                    "project_path": "/tmp/app-a",
                    "key": "web",
                    "protocol": "",
                    "description": "",
                    "registered_at": "2026-01-01T00:00:00Z",
                },
                "3001": {
                    "project": "app-a",
                    "project_path": "/tmp/app-a",
                    "key": "api",
                    "protocol": "",
                    "description": "",
                    "registered_at": "2026-01-01T00:00:00Z",
                },
                "4000": {
                    "project": "app-b",
                    "project_path": "/tmp/app-b",
                    "key": "web",
                    "protocol": "",
                    "description": "",
                    "registered_at": "2026-01-01T00:00:00Z",
                },
            },
        }

        grouped = list_ports_by_project(registry)

        assert len(grouped) == 2
        assert len(grouped["app-a"]) == 2
        assert len(grouped["app-b"]) == 1
        # Should be sorted by port number
        assert grouped["app-a"][0]["port"] == 3000
        assert grouped["app-a"][1]["port"] == 3001

    def test_empty_registry_returns_empty_dict(self):
        """Should return empty dict for empty registry."""
        from aec.lib.ports import list_ports_by_project

        registry = {"version": "1.0.0", "ports": {}}
        grouped = list_ports_by_project(registry)
        assert grouped == {}
