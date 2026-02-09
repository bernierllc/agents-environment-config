"""Tests for the agent registry (agents.json and aec/lib/registry.py)."""

import json
import subprocess
from pathlib import Path

import pytest

from aec.lib.registry import (
    load_agent_registry,
    get_supported_agents,
    get_agent_files,
    get_gitignore_patterns,
    get_migration_files,
    get_generation_agents,
    invalidate_cache,
)


# Locate repo root and agents.json
REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_JSON = REPO_ROOT / "agents.json"


@pytest.fixture(autouse=True)
def _clear_registry_cache():
    """Clear the registry cache before each test so we always read fresh data."""
    invalidate_cache()
    yield
    invalidate_cache()


class TestAgentsJsonSchema:
    """Validate the agents.json file structure."""

    def test_agents_json_exists(self):
        assert AGENTS_JSON.exists(), "agents.json must exist at repo root"

    def test_agents_json_is_valid_json(self):
        with open(AGENTS_JSON) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_has_schema_version(self):
        with open(AGENTS_JSON) as f:
            data = json.load(f)
        assert "_schema_version" in data

    def test_has_agents_key(self):
        with open(AGENTS_JSON) as f:
            data = json.load(f)
        assert "agents" in data
        assert isinstance(data["agents"], dict)

    def test_each_agent_has_required_fields(self):
        with open(AGENTS_JSON) as f:
            data = json.load(f)

        required_fields = {
            "display_name",
            "description",
            "instruction_file",
            "commands",
            "alt_paths",
            "terminal_launch",
            "has_resume",
        }

        for name, agent in data["agents"].items():
            for field in required_fields:
                assert field in agent, (
                    f"Agent '{name}' missing required field '{field}'"
                )

    def test_commands_are_lists_of_strings(self):
        with open(AGENTS_JSON) as f:
            data = json.load(f)

        for name, agent in data["agents"].items():
            assert isinstance(agent["commands"], list), (
                f"Agent '{name}' commands must be a list"
            )
            assert len(agent["commands"]) > 0, (
                f"Agent '{name}' must have at least one command"
            )
            for cmd in agent["commands"]:
                assert isinstance(cmd, str), (
                    f"Agent '{name}' has non-string command"
                )

    def test_alt_paths_are_lists_of_strings(self):
        with open(AGENTS_JSON) as f:
            data = json.load(f)

        for name, agent in data["agents"].items():
            assert isinstance(agent["alt_paths"], list), (
                f"Agent '{name}' alt_paths must be a list"
            )
            for p in agent["alt_paths"]:
                assert isinstance(p, str), (
                    f"Agent '{name}' has non-string in alt_paths"
                )

    def test_terminal_launch_is_bool(self):
        with open(AGENTS_JSON) as f:
            data = json.load(f)

        for name, agent in data["agents"].items():
            assert isinstance(agent["terminal_launch"], bool), (
                f"Agent '{name}' terminal_launch must be bool"
            )

    def test_has_resume_is_bool(self):
        with open(AGENTS_JSON) as f:
            data = json.load(f)

        for name, agent in data["agents"].items():
            assert isinstance(agent["has_resume"], bool), (
                f"Agent '{name}' has_resume must be bool"
            )

    def test_instruction_file_is_string_or_null(self):
        with open(AGENTS_JSON) as f:
            data = json.load(f)

        for name, agent in data["agents"].items():
            val = agent["instruction_file"]
            assert val is None or isinstance(val, str), (
                f"Agent '{name}' instruction_file must be string or null"
            )

    def test_terminal_agents_have_launch_args(self):
        with open(AGENTS_JSON) as f:
            data = json.load(f)

        for name, agent in data["agents"].items():
            if agent["terminal_launch"]:
                assert "launch_args" in agent, (
                    f"Terminal agent '{name}' missing launch_args"
                )

    def test_non_terminal_agents_have_launch_template(self):
        with open(AGENTS_JSON) as f:
            data = json.load(f)

        for name, agent in data["agents"].items():
            if not agent["terminal_launch"]:
                assert "launch_template" in agent, (
                    f"Non-terminal agent '{name}' missing launch_template"
                )

    def test_resume_agents_have_resume_args(self):
        with open(AGENTS_JSON) as f:
            data = json.load(f)

        for name, agent in data["agents"].items():
            if agent["has_resume"]:
                assert "resume_args" in agent, (
                    f"Agent '{name}' has_resume=true but missing resume_args"
                )


class TestLoadAgentRegistry:
    """Test the registry loader function."""

    def test_returns_dict(self):
        result = load_agent_registry()
        assert isinstance(result, dict)

    def test_has_agents(self):
        result = load_agent_registry()
        assert "agents" in result
        assert len(result["agents"]) > 0

    def test_caching_returns_same_object(self):
        first = load_agent_registry()
        second = load_agent_registry()
        assert first is second


class TestGetSupportedAgents:
    """Test the SUPPORTED_AGENTS-compatible output."""

    def test_returns_dict(self):
        result = get_supported_agents()
        assert isinstance(result, dict)

    def test_all_expected_agents_present(self):
        """All agents from agents.json should appear."""
        with open(AGENTS_JSON) as f:
            data = json.load(f)
        expected = set(data["agents"].keys())
        actual = set(get_supported_agents().keys())
        assert actual == expected

    def test_each_agent_has_required_keys(self):
        required_keys = {"commands", "alt_paths", "terminal_launch", "has_resume"}
        for name, config in get_supported_agents().items():
            for key in required_keys:
                assert key in config, (
                    f"Agent '{name}' missing required key '{key}'"
                )

    def test_alt_paths_are_path_objects(self):
        for name, config in get_supported_agents().items():
            for p in config["alt_paths"]:
                assert isinstance(p, Path), (
                    f"Agent '{name}' alt_path should be Path, got {type(p)}"
                )

    def test_claude_has_resume_args(self):
        agents = get_supported_agents()
        assert agents["claude"]["has_resume"] is True
        assert "resume_args" in agents["claude"]

    def test_cursor_is_not_terminal_launch(self):
        agents = get_supported_agents()
        assert agents["cursor"]["terminal_launch"] is False
        assert "launch_template" in agents["cursor"]


class TestGetAgentFiles:
    """Test the agent files list."""

    def test_always_includes_agentinfo(self):
        files = get_agent_files()
        assert "AGENTINFO.md" in files
        assert files[0] == "AGENTINFO.md"

    def test_includes_all_instruction_files(self):
        with open(AGENTS_JSON) as f:
            data = json.load(f)

        files = get_agent_files()
        for agent in data["agents"].values():
            f_name = agent.get("instruction_file")
            if f_name:
                assert f_name in files, f"{f_name} should be in agent files"

    def test_no_duplicates(self):
        files = get_agent_files()
        assert len(files) == len(set(files))

    def test_null_instruction_files_excluded(self):
        """Agents with instruction_file=null should not appear."""
        files = get_agent_files()
        assert None not in files


class TestGetGitignorePatterns:
    """Test gitignore pattern generation."""

    def test_includes_agent_files(self):
        patterns = get_gitignore_patterns()
        files = get_agent_files()
        for f in files:
            assert f in patterns

    def test_includes_cursor_rules(self):
        patterns = get_gitignore_patterns()
        assert ".cursor/rules" in patterns

    def test_includes_plans(self):
        patterns = get_gitignore_patterns()
        assert "/plans/" in patterns


class TestGetMigrationFiles:
    """Test migration file list."""

    def test_only_includes_use_agent_rules(self):
        with open(AGENTS_JSON) as f:
            data = json.load(f)

        migration = get_migration_files()
        for agent in data["agents"].values():
            f_name = agent.get("instruction_file")
            if agent.get("use_agent_rules") and f_name:
                assert f_name in migration
            elif f_name and not agent.get("use_agent_rules"):
                assert f_name not in migration

    def test_cursor_not_in_migration(self):
        """Cursor has no instruction_file, should not appear."""
        migration = get_migration_files()
        assert None not in migration


class TestGetGenerationAgents:
    """Test generation agents dict."""

    def test_returns_dict(self):
        result = get_generation_agents()
        assert isinstance(result, dict)

    def test_each_entry_is_tuple(self):
        for filename, entry in get_generation_agents().items():
            assert isinstance(entry, tuple)
            assert len(entry) == 2
            assert isinstance(entry[0], str)  # display_name
            assert isinstance(entry[1], bool)  # use_agent_rules

    def test_matches_agents_json(self):
        with open(AGENTS_JSON) as f:
            data = json.load(f)

        gen_agents = get_generation_agents()
        for agent in data["agents"].values():
            f_name = agent.get("instruction_file")
            if f_name:
                assert f_name in gen_agents
                assert gen_agents[f_name][0] == agent["display_name"]


class TestShellConfigFreshness:
    """Verify that _agent-config.sh matches what would be generated from agents.json."""

    def test_agent_config_sh_exists(self):
        config_sh = REPO_ROOT / "scripts" / "_agent-config.sh"
        assert config_sh.exists(), (
            "scripts/_agent-config.sh not found. "
            "Run: python3 scripts/generate-agent-config.py"
        )

    def test_agent_config_sh_is_fresh(self):
        """Regenerating should produce identical content."""
        config_sh = REPO_ROOT / "scripts" / "_agent-config.sh"
        existing_content = config_sh.read_text()

        result = subprocess.run(
            ["python3", str(REPO_ROOT / "scripts" / "generate-agent-config.py")],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"Generator failed: {result.stderr}"

        new_content = config_sh.read_text()
        assert existing_content == new_content, (
            "scripts/_agent-config.sh is stale. "
            "Run: python3 scripts/generate-agent-config.py"
        )
