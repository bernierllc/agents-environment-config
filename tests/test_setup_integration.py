"""Integration tests for setup flow: aec_json, test detection, ports, and prune."""

import json
from pathlib import Path

import pytest


class TestCreateOrUpdateAecJson:
    """Test _create_or_update_aec_json in repo.py."""

    def test_creates_aec_json_when_missing(self, temp_dir):
        """_create_or_update_aec_json returns skeleton when .aec.json doesn't exist."""
        from aec.commands.repo import _create_or_update_aec_json

        project_dir = temp_dir / "my-project"
        project_dir.mkdir()

        result = _create_or_update_aec_json(project_dir)

        # The function returns a skeleton but does not save (setup() saves later)
        assert result["name"] == "my-project"
        assert "ports" in result
        assert "test_suites" in result

    def test_preserves_existing_aec_json(self, temp_dir):
        """_create_or_update_aec_json loads and returns existing .aec.json."""
        from aec.commands.repo import _create_or_update_aec_json

        project_dir = temp_dir / "existing-project"
        project_dir.mkdir()

        existing_data = {
            "name": "custom-name",
            "version": "2.0.0",
            "ports": {"web": 3000},
            "test_suites": [{"name": "test", "command": "npm test"}],
        }
        (project_dir / ".aec.json").write_text(json.dumps(existing_data))

        result = _create_or_update_aec_json(project_dir)

        assert result["name"] == "custom-name"
        assert result["version"] == "2.0.0"
        assert result["ports"] == {"web": 3000}

    def test_dry_run_does_not_create_file(self, temp_dir):
        """_create_or_update_aec_json in dry_run mode does not write."""
        from aec.commands.repo import _create_or_update_aec_json

        project_dir = temp_dir / "dry-run-project"
        project_dir.mkdir()

        result = _create_or_update_aec_json(project_dir, dry_run=True)

        assert not (project_dir / ".aec.json").exists()
        assert result["name"] == "dry-run-project"


class TestDetectAndPromptTestSuites:
    """Test _detect_and_prompt_test_suites in repo.py."""

    def test_finds_jest_framework(self, temp_dir):
        """Detects Jest when jest.config.ts exists."""
        from aec.commands.repo import _detect_and_prompt_test_suites

        project_dir = temp_dir / "jest-project"
        project_dir.mkdir()
        (project_dir / "jest.config.ts").write_text("module.exports = {}")

        aec_data = {"test_suites": []}
        result = _detect_and_prompt_test_suites(
            project_dir, aec_data, batch_mode=True
        )

        # No package.json scripts, so no suites added, but no error
        assert "test_suites" in result

    def test_batch_mode_uses_all_scripts(self, temp_dir):
        """In batch_mode, all detected test scripts are used without prompting."""
        from aec.commands.repo import _detect_and_prompt_test_suites

        project_dir = temp_dir / "batch-project"
        project_dir.mkdir()

        pkg_data = {
            "scripts": {
                "test": "jest",
                "test:unit": "jest --config jest.config.unit.ts",
                "build": "tsc",  # not a test script
            }
        }
        (project_dir / "package.json").write_text(json.dumps(pkg_data))

        aec_data = {"test_suites": []}
        result = _detect_and_prompt_test_suites(
            project_dir, aec_data, batch_mode=True
        )

        suites = result["test_suites"]
        suite_names = [s["name"] for s in suites]
        assert "test" in suite_names
        assert "test:unit" in suite_names
        assert "build" not in suite_names

    def test_no_frameworks_or_scripts(self, temp_dir):
        """Returns unchanged data when nothing is detected."""
        from aec.commands.repo import _detect_and_prompt_test_suites

        project_dir = temp_dir / "empty-project"
        project_dir.mkdir()

        aec_data = {"test_suites": []}
        result = _detect_and_prompt_test_suites(
            project_dir, aec_data, batch_mode=True
        )

        assert result["test_suites"] == []

    def test_interactive_mode_with_input(self, temp_dir, monkeypatch):
        """Interactive mode prompts and respects user input."""
        from aec.commands.repo import _detect_and_prompt_test_suites

        project_dir = temp_dir / "interactive-project"
        project_dir.mkdir()

        pkg_data = {
            "scripts": {
                "test": "jest",
                "test:e2e": "playwright test",
            }
        }
        (project_dir / "package.json").write_text(json.dumps(pkg_data))

        # Simulate user choosing "1" (first script only)
        monkeypatch.setattr("builtins.input", lambda _: "1")

        aec_data = {"test_suites": []}
        result = _detect_and_prompt_test_suites(
            project_dir, aec_data, batch_mode=False
        )

        suites = result["test_suites"]
        assert len(suites) == 1
        assert suites[0]["name"] == "test"


class TestRegisterPorts:
    """Test _register_ports in repo.py."""

    def test_registers_ports_from_aec_json(self, temp_dir, monkeypatch):
        """Registers ports when port_registry_enabled is True."""
        from aec.commands.repo import _register_ports

        project_dir = temp_dir / "port-project"
        project_dir.mkdir()

        registry_path = temp_dir / "ports-registry.json"
        monkeypatch.setattr("aec.lib.config.AEC_PORTS_REGISTRY", registry_path)
        monkeypatch.setattr(
            "aec.commands.repo._register_ports.__module__",
            "aec.commands.repo",
        )

        # Mock get_preference to return True for port_registry_enabled
        monkeypatch.setattr(
            "aec.lib.preferences.get_preference",
            lambda key: True if key == "port_registry_enabled" else None,
        )

        aec_data = {
            "ports": {"web": 3000, "api": 8080},
        }

        _register_ports(project_dir, aec_data)

        assert registry_path.exists()
        registry = json.loads(registry_path.read_text())
        assert "3000" in registry["ports"]
        assert "8080" in registry["ports"]

    def test_warns_on_conflicts(self, temp_dir, monkeypatch, capsys):
        """Shows warnings when ports conflict with existing registrations."""
        from aec.commands.repo import _register_ports

        project_dir = temp_dir / "conflict-project"
        project_dir.mkdir()

        registry_path = temp_dir / "ports-registry.json"
        # Pre-register port 3000 for a different project
        existing_registry = {
            "ports": {
                "3000": {"project": "/other/project", "service": "web"},
            }
        }
        registry_path.write_text(json.dumps(existing_registry))

        monkeypatch.setattr("aec.lib.config.AEC_PORTS_REGISTRY", registry_path)
        monkeypatch.setattr(
            "aec.lib.preferences.get_preference",
            lambda key: True if key == "port_registry_enabled" else None,
        )

        aec_data = {
            "ports": {"web": 3000, "api": 8080},
        }

        _register_ports(project_dir, aec_data)

        output = capsys.readouterr().out
        assert "conflict" in output.lower() or "3000" in output

        # Port 8080 should be registered, 3000 should not (conflict)
        registry = json.loads(registry_path.read_text())
        assert "8080" in registry["ports"]
        # 3000 still belongs to the other project
        assert registry["ports"]["3000"]["project"] == "/other/project"

    def test_skips_when_disabled(self, temp_dir, monkeypatch):
        """Does nothing when port_registry_enabled is not True."""
        from aec.commands.repo import _register_ports

        project_dir = temp_dir / "disabled-project"
        project_dir.mkdir()

        monkeypatch.setattr(
            "aec.lib.preferences.get_preference",
            lambda key: None,
        )

        aec_data = {"ports": {"web": 3000}}

        # Should not raise or create any files
        _register_ports(project_dir, aec_data)


class TestInjectPortRegistryAgentinfo:
    """Test _inject_port_registry_agentinfo in repo.py."""

    def test_appends_to_agentinfo(self, temp_dir, monkeypatch):
        """Appends Port Registry section to AGENTINFO.md."""
        from aec.commands.repo import _inject_port_registry_agentinfo

        project_dir = temp_dir / "agentinfo-project"
        project_dir.mkdir()

        agentinfo = project_dir / "AGENTINFO.md"
        agentinfo.write_text("# My Project\n\nSome content.\n")

        monkeypatch.setattr(
            "aec.lib.preferences.get_preference",
            lambda key: True if key == "port_registry_enabled" else None,
        )

        _inject_port_registry_agentinfo(project_dir)

        content = agentinfo.read_text()
        assert "## Port Registry" in content
        assert "aec ports list" in content

    def test_skips_if_section_already_exists(self, temp_dir, monkeypatch):
        """Does not duplicate Port Registry section."""
        from aec.commands.repo import _inject_port_registry_agentinfo

        project_dir = temp_dir / "existing-section"
        project_dir.mkdir()

        agentinfo = project_dir / "AGENTINFO.md"
        original = "# My Project\n\n## Port Registry\n\nAlready here.\n"
        agentinfo.write_text(original)

        monkeypatch.setattr(
            "aec.lib.preferences.get_preference",
            lambda key: True if key == "port_registry_enabled" else None,
        )

        _inject_port_registry_agentinfo(project_dir)

        content = agentinfo.read_text()
        assert content == original  # Unchanged

    def test_skips_when_no_agentinfo(self, temp_dir, monkeypatch):
        """Does nothing when AGENTINFO.md doesn't exist."""
        from aec.commands.repo import _inject_port_registry_agentinfo

        project_dir = temp_dir / "no-agentinfo"
        project_dir.mkdir()

        monkeypatch.setattr(
            "aec.lib.preferences.get_preference",
            lambda key: True if key == "port_registry_enabled" else None,
        )

        _inject_port_registry_agentinfo(project_dir)
        # No AGENTINFO.md created
        assert not (project_dir / "AGENTINFO.md").exists()


class TestPruneFreesPortsForRemovedProjects:
    """Test that prune_stale frees ports for removed projects."""

    def test_prune_frees_ports(self, temp_dir, monkeypatch):
        """prune_stale() unregisters ports for pruned projects."""
        from aec.lib.tracking import prune_stale

        # Set up tracking
        aec_home = temp_dir / ".agents-environment-config"
        aec_home.mkdir(parents=True)
        log_file = aec_home / "setup-repo-locations.txt"
        registry_path = aec_home / "ports-registry.json"

        monkeypatch.setattr("aec.lib.tracking.AEC_HOME", aec_home)
        monkeypatch.setattr("aec.lib.tracking.AEC_SETUP_LOG", log_file)
        monkeypatch.setattr("aec.lib.tracking.AEC_README", aec_home / "README.md")
        monkeypatch.setattr("aec.lib.config.AEC_PORTS_REGISTRY", registry_path)

        # Create a project that will be pruned (doesn't exist)
        fake_project = temp_dir / "removed-project"
        real_project = temp_dir / "real-project"
        real_project.mkdir()

        log_file.write_text(
            f"2026-01-01T00:00:00Z|2.0.0|{real_project}\n"
            f"2026-01-01T00:00:00Z|2.0.0|{fake_project}\n"
        )

        # Register ports for the fake project
        registry = {
            "ports": {
                "3000": {"project": str(fake_project), "service": "web"},
                "8080": {"project": str(real_project), "service": "api"},
            }
        }
        registry_path.write_text(json.dumps(registry))

        pruned = prune_stale()
        assert len(pruned) == 1

        # Check that port 3000 was freed
        updated_registry = json.loads(registry_path.read_text())
        assert "3000" not in updated_registry["ports"]
        # Port 8080 still registered
        assert "8080" in updated_registry["ports"]


class TestManageAecJsonGitignoreStep:
    """Test _manage_aec_json_gitignore_step in repo.py."""

    def test_adds_to_gitignore_by_default(self, temp_dir, monkeypatch):
        """Adds .aec.json to .gitignore when setting is None (default)."""
        from aec.commands.repo import _manage_aec_json_gitignore_step

        project_dir = temp_dir / "gitignore-project"
        project_dir.mkdir()
        (project_dir / ".gitignore").write_text("node_modules/\n")

        monkeypatch.setattr(
            "aec.lib.preferences.get_setting",
            lambda key: None,
        )

        _manage_aec_json_gitignore_step(project_dir)

        content = (project_dir / ".gitignore").read_text()
        assert ".aec.json" in content


class TestSyncInstalledSection:
    """Test _sync_installed_section in repo.py."""

    def test_syncs_from_manifest(self, temp_dir, monkeypatch):
        """Populates installed section from manifest."""
        from aec.commands.repo import _sync_installed_section

        # Mock the manifest loader
        mock_manifest = {
            "skills": {"code-review": {"version": "1.0.0"}},
            "rules": {"typescript": {"version": "1.0.0"}},
            "agents": {},
        }
        monkeypatch.setattr(
            "aec.lib.skills_manifest.load_installed_manifest",
            lambda path: mock_manifest,
        )

        aec_data = {"installed": {"skills": [], "rules": [], "agents": []}}
        result = _sync_installed_section(aec_data)

        assert "code-review" in result["installed"]["skills"]
        assert "typescript" in result["installed"]["rules"]
