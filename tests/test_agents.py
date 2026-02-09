"""Tests for agent detection and Raycast script generation."""

import json
import os
import shutil
import stat
from pathlib import Path

import pytest

from aec.lib.config import (
    detect_agents,
    generate_raycast_script,
)
from aec.lib.registry import get_supported_agents, load_agent_registry

# Load SUPPORTED_AGENTS from registry (not hardcoded)
SUPPORTED_AGENTS = get_supported_agents()

# Derive expected agent names from agents.json
REPO_ROOT = Path(__file__).resolve().parent.parent
with open(REPO_ROOT / "agents.json") as _f:
    _REGISTRY = json.load(_f)
EXPECTED_AGENT_NAMES = set(_REGISTRY["agents"].keys())


class TestSupportedAgents:
    """Test the SUPPORTED_AGENTS configuration structure."""

    def test_all_expected_agents_present(self):
        """All expected agents from agents.json should be defined."""
        assert set(SUPPORTED_AGENTS.keys()) == EXPECTED_AGENT_NAMES

    def test_each_agent_has_required_keys(self):
        """Every agent config must have the required keys."""
        required_keys = {"commands", "alt_paths", "terminal_launch", "has_resume"}
        for name, config in SUPPORTED_AGENTS.items():
            for key in required_keys:
                assert key in config, f"Agent '{name}' missing required key '{key}'"

    def test_commands_are_lists(self):
        """Commands should be lists of strings."""
        for name, config in SUPPORTED_AGENTS.items():
            assert isinstance(config["commands"], list), f"Agent '{name}' commands not a list"
            assert len(config["commands"]) > 0, f"Agent '{name}' has no commands"
            for cmd in config["commands"]:
                assert isinstance(cmd, str), f"Agent '{name}' has non-string command"

    def test_alt_paths_are_lists(self):
        """Alt paths should be lists of Path objects."""
        for name, config in SUPPORTED_AGENTS.items():
            assert isinstance(config["alt_paths"], list), f"Agent '{name}' alt_paths not a list"
            for p in config["alt_paths"]:
                assert isinstance(p, Path), f"Agent '{name}' has non-Path in alt_paths"

    def test_terminal_agents_have_launch_args(self):
        """Terminal-launched agents should have launch_args defined."""
        for name, config in SUPPORTED_AGENTS.items():
            if config["terminal_launch"]:
                assert "launch_args" in config, f"Agent '{name}' missing launch_args"

    def test_resume_agents_have_resume_args(self):
        """Agents with has_resume=True must have resume_args."""
        for name, config in SUPPORTED_AGENTS.items():
            if config["has_resume"]:
                assert "resume_args" in config, f"Agent '{name}' has resume but no resume_args"


# ---------------------------------------------------------------------------
# Per-agent exact config value tests
# These catch regressions if someone changes a value in agents.json
# ---------------------------------------------------------------------------


class TestClaudeConfig:
    """Validate Claude Code exact configuration values."""

    def test_command(self):
        assert SUPPORTED_AGENTS["claude"]["commands"] == ["claude"]

    def test_terminal_launch(self):
        assert SUPPORTED_AGENTS["claude"]["terminal_launch"] is True

    def test_launch_args(self):
        assert SUPPORTED_AGENTS["claude"]["launch_args"] == "--dangerously-skip-permissions"

    def test_has_resume(self):
        assert SUPPORTED_AGENTS["claude"]["has_resume"] is True

    def test_resume_args(self):
        assert SUPPORTED_AGENTS["claude"]["resume_args"] == "--dangerously-skip-permissions --resume"

    def test_alt_paths(self):
        alt_paths = SUPPORTED_AGENTS["claude"]["alt_paths"]
        assert len(alt_paths) == 1
        assert alt_paths[0] == Path.home() / ".claude"

    def test_instruction_file(self):
        assert _REGISTRY["agents"]["claude"]["instruction_file"] == "CLAUDE.md"

    def test_use_agent_rules(self):
        assert _REGISTRY["agents"]["claude"]["use_agent_rules"] is True


class TestCursorConfig:
    """Validate Cursor exact configuration values."""

    def test_command(self):
        assert SUPPORTED_AGENTS["cursor"]["commands"] == ["cursor"]

    def test_terminal_launch(self):
        assert SUPPORTED_AGENTS["cursor"]["terminal_launch"] is False

    def test_launch_template(self):
        assert SUPPORTED_AGENTS["cursor"]["launch_template"] == "cursor {path}/"

    def test_has_resume(self):
        assert SUPPORTED_AGENTS["cursor"]["has_resume"] is False

    def test_alt_paths(self):
        alt_paths = SUPPORTED_AGENTS["cursor"]["alt_paths"]
        assert len(alt_paths) == 1
        assert alt_paths[0] == Path("/Applications/Cursor.app")

    def test_instruction_file_is_null(self):
        assert _REGISTRY["agents"]["cursor"]["instruction_file"] is None

    def test_use_agent_rules(self):
        assert _REGISTRY["agents"]["cursor"]["use_agent_rules"] is False


class TestGeminiConfig:
    """Validate Gemini CLI exact configuration values."""

    def test_command(self):
        assert SUPPORTED_AGENTS["gemini"]["commands"] == ["gemini"]

    def test_terminal_launch(self):
        assert SUPPORTED_AGENTS["gemini"]["terminal_launch"] is True

    def test_launch_args(self):
        assert SUPPORTED_AGENTS["gemini"]["launch_args"] == "--yolo"

    def test_has_resume(self):
        assert SUPPORTED_AGENTS["gemini"]["has_resume"] is True

    def test_resume_args(self):
        assert SUPPORTED_AGENTS["gemini"]["resume_args"] == "--yolo --resume"

    def test_alt_paths_empty(self):
        assert SUPPORTED_AGENTS["gemini"]["alt_paths"] == []

    def test_instruction_file(self):
        assert _REGISTRY["agents"]["gemini"]["instruction_file"] == "GEMINI.md"

    def test_use_agent_rules(self):
        assert _REGISTRY["agents"]["gemini"]["use_agent_rules"] is True


class TestQwenConfig:
    """Validate Qwen Code exact configuration values."""

    def test_command(self):
        assert SUPPORTED_AGENTS["qwen"]["commands"] == ["qwen"]

    def test_terminal_launch(self):
        assert SUPPORTED_AGENTS["qwen"]["terminal_launch"] is True

    def test_launch_args(self):
        assert SUPPORTED_AGENTS["qwen"]["launch_args"] == "--yolo"

    def test_has_resume(self):
        assert SUPPORTED_AGENTS["qwen"]["has_resume"] is True

    def test_resume_args(self):
        assert SUPPORTED_AGENTS["qwen"]["resume_args"] == "--yolo --continue"

    def test_alt_paths_empty(self):
        assert SUPPORTED_AGENTS["qwen"]["alt_paths"] == []

    def test_instruction_file(self):
        assert _REGISTRY["agents"]["qwen"]["instruction_file"] == "QWEN.md"

    def test_use_agent_rules(self):
        assert _REGISTRY["agents"]["qwen"]["use_agent_rules"] is True


class TestCodexConfig:
    """Validate Codex exact configuration values."""

    def test_command(self):
        assert SUPPORTED_AGENTS["codex"]["commands"] == ["codex"]

    def test_terminal_launch(self):
        assert SUPPORTED_AGENTS["codex"]["terminal_launch"] is True

    def test_launch_args(self):
        assert SUPPORTED_AGENTS["codex"]["launch_args"] == "--dangerously-bypass-approvals-and-sandbox"

    def test_has_resume(self):
        assert SUPPORTED_AGENTS["codex"]["has_resume"] is True

    def test_resume_args(self):
        assert SUPPORTED_AGENTS["codex"]["resume_args"] == "resume --last"

    def test_alt_paths_empty(self):
        assert SUPPORTED_AGENTS["codex"]["alt_paths"] == []

    def test_instruction_file(self):
        assert _REGISTRY["agents"]["codex"]["instruction_file"] == "AGENTS.md"

    def test_use_agent_rules(self):
        assert _REGISTRY["agents"]["codex"]["use_agent_rules"] is True


# ---------------------------------------------------------------------------
# Instruction file existence tests
# ---------------------------------------------------------------------------


class TestInstructionFilesExist:
    """Every non-null instruction_file in agents.json must exist at repo root."""

    def test_all_instruction_files_exist(self):
        for name, agent in _REGISTRY["agents"].items():
            f_name = agent.get("instruction_file")
            if f_name:
                filepath = REPO_ROOT / f_name
                assert filepath.exists(), (
                    f"Agent '{name}' instruction_file '{f_name}' "
                    f"does not exist at {filepath}"
                )

    def test_agentinfo_template_exists(self):
        """AGENTINFO.md must always exist (it's included in every setup)."""
        assert (REPO_ROOT / "AGENTINFO.md").exists()


# ---------------------------------------------------------------------------
# Shell config variable value spot-checks
# ---------------------------------------------------------------------------


class TestShellConfigValues:
    """Parse _agent-config.sh and verify key variables match agents.json."""

    @pytest.fixture(autouse=True)
    def _load_shell_config(self):
        config_path = REPO_ROOT / "scripts" / "_agent-config.sh"
        assert config_path.exists(), "_agent-config.sh must exist"
        self.shell_content = config_path.read_text()

    def _get_shell_var(self, var_name: str) -> str:
        """Extract a variable value from the shell config."""
        for line in self.shell_content.splitlines():
            if line.startswith(f"{var_name}="):
                # Strip var_name= and surrounding quotes
                value = line[len(var_name) + 1:]
                return value.strip('"')
        pytest.fail(f"Variable {var_name} not found in _agent-config.sh")

    def test_claude_launch_args(self):
        assert self._get_shell_var("AGENT_claude_LAUNCH_ARGS") == "--dangerously-skip-permissions"

    def test_claude_resume_args(self):
        assert self._get_shell_var("AGENT_claude_RESUME_ARGS") == "--dangerously-skip-permissions --resume"

    def test_claude_has_resume(self):
        assert self._get_shell_var("AGENT_claude_HAS_RESUME") == "true"

    def test_cursor_terminal_launch_false(self):
        assert self._get_shell_var("AGENT_cursor_TERMINAL_LAUNCH") == "false"

    def test_cursor_launch_template(self):
        assert self._get_shell_var("AGENT_cursor_LAUNCH_TEMPLATE") == "cursor {path}/"

    def test_cursor_has_resume_false(self):
        assert self._get_shell_var("AGENT_cursor_HAS_RESUME") == "false"

    def test_gemini_launch_args(self):
        assert self._get_shell_var("AGENT_gemini_LAUNCH_ARGS") == "--yolo"

    def test_gemini_resume_args(self):
        assert self._get_shell_var("AGENT_gemini_RESUME_ARGS") == "--yolo --resume"

    def test_qwen_launch_args(self):
        assert self._get_shell_var("AGENT_qwen_LAUNCH_ARGS") == "--yolo"

    def test_qwen_resume_args(self):
        assert self._get_shell_var("AGENT_qwen_RESUME_ARGS") == "--yolo --continue"

    def test_codex_launch_args(self):
        assert self._get_shell_var("AGENT_codex_LAUNCH_ARGS") == "--dangerously-bypass-approvals-and-sandbox"

    def test_codex_resume_args(self):
        assert self._get_shell_var("AGENT_codex_RESUME_ARGS") == "resume --last"

    def test_all_agents_have_display_name(self):
        for name in _REGISTRY["agents"]:
            var = f"AGENT_{name}_DISPLAY_NAME"
            value = self._get_shell_var(var)
            assert value == _REGISTRY["agents"][name]["display_name"]

    def test_all_agents_have_commands(self):
        for name in _REGISTRY["agents"]:
            var = f"AGENT_{name}_COMMANDS"
            value = self._get_shell_var(var)
            expected = " ".join(_REGISTRY["agents"][name]["commands"])
            assert value == expected


# ---------------------------------------------------------------------------
# Raycast launch command output tests (Python generate_raycast_script)
# ---------------------------------------------------------------------------


class TestRaycastOutputPerAgent:
    """Validate the Python generate_raycast_script produces correct launch commands."""

    PROJECT_PATH = "/Users/dev/projects/my-app"

    def test_claude_launch(self):
        content = generate_raycast_script(
            "claude", SUPPORTED_AGENTS["claude"], "my-app", self.PROJECT_PATH
        )
        assert "osascript -e" in content
        assert "claude --dangerously-skip-permissions" in content
        assert f"cd {self.PROJECT_PATH}/" in content

    def test_claude_resume(self):
        content = generate_raycast_script(
            "claude", SUPPORTED_AGENTS["claude"], "my-app", self.PROJECT_PATH, is_resume=True
        )
        assert "--dangerously-skip-permissions --resume" in content

    def test_cursor_launch(self):
        content = generate_raycast_script(
            "cursor", SUPPORTED_AGENTS["cursor"], "my-app", self.PROJECT_PATH
        )
        assert f"cursor {self.PROJECT_PATH}/" in content
        assert "osascript" not in content

    def test_gemini_launch(self):
        content = generate_raycast_script(
            "gemini", SUPPORTED_AGENTS["gemini"], "my-app", self.PROJECT_PATH
        )
        assert "osascript -e" in content
        assert "gemini --yolo" in content
        assert f"cd {self.PROJECT_PATH}/" in content

    def test_gemini_resume(self):
        content = generate_raycast_script(
            "gemini", SUPPORTED_AGENTS["gemini"], "my-app", self.PROJECT_PATH, is_resume=True
        )
        assert "--yolo --resume" in content

    def test_qwen_launch(self):
        content = generate_raycast_script(
            "qwen", SUPPORTED_AGENTS["qwen"], "my-app", self.PROJECT_PATH
        )
        assert "osascript -e" in content
        assert "qwen --yolo" in content
        assert f"cd {self.PROJECT_PATH}/" in content

    def test_qwen_resume(self):
        content = generate_raycast_script(
            "qwen", SUPPORTED_AGENTS["qwen"], "my-app", self.PROJECT_PATH, is_resume=True
        )
        assert "--yolo --continue" in content

    def test_codex_launch(self):
        content = generate_raycast_script(
            "codex", SUPPORTED_AGENTS["codex"], "my-app", self.PROJECT_PATH
        )
        assert "osascript -e" in content
        assert "codex --dangerously-bypass-approvals-and-sandbox" in content
        assert f"cd {self.PROJECT_PATH}/" in content

    def test_codex_resume(self):
        content = generate_raycast_script(
            "codex", SUPPORTED_AGENTS["codex"], "my-app", self.PROJECT_PATH, is_resume=True
        )
        assert "codex resume --last" in content

    def test_all_scripts_have_shebang(self):
        for name, config in SUPPORTED_AGENTS.items():
            content = generate_raycast_script(name, config, "test", "/tmp/test")
            assert content.startswith("#!/bin/bash"), f"{name} missing shebang"

    def test_all_scripts_have_raycast_metadata(self):
        for name, config in SUPPORTED_AGENTS.items():
            content = generate_raycast_script(name, config, "test-proj", "/tmp/test")
            assert "@raycast.schemaVersion 1" in content, f"{name} missing schemaVersion"
            assert f"@raycast.title {name} test-proj" in content, f"{name} missing title"

    def test_resume_scripts_have_resume_in_title(self):
        for name, config in SUPPORTED_AGENTS.items():
            if config["has_resume"]:
                content = generate_raycast_script(
                    name, config, "proj", "/tmp/proj", is_resume=True
                )
                assert f"@raycast.title {name} proj resume" in content, (
                    f"{name} resume script missing 'resume' in title"
                )


# ---------------------------------------------------------------------------
# Detection logic tests (mock-based)
# ---------------------------------------------------------------------------


class TestDetectAgents:
    """Test agent detection logic."""

    def test_detects_agent_via_command(self, monkeypatch):
        """Should detect agent when its command is on PATH."""
        def mock_which(cmd):
            if cmd == "claude":
                return "/usr/local/bin/claude"
            return None

        monkeypatch.setattr("shutil.which", mock_which)
        monkeypatch.setattr(
            "aec.lib.config.SUPPORTED_AGENTS",
            {
                "claude": {
                    "commands": ["claude"],
                    "alt_paths": [],
                    "terminal_launch": True,
                    "launch_args": "--dangerously-skip-permissions",
                    "has_resume": True,
                    "resume_args": "--dangerously-skip-permissions --resume",
                },
            },
        )

        detected = detect_agents()
        assert "claude" in detected

    def test_detects_agent_via_alt_path(self, tmp_path, monkeypatch):
        """Should detect agent when alt_path exists even without command."""
        def mock_which(cmd):
            return None

        monkeypatch.setattr("shutil.which", mock_which)

        alt_dir = tmp_path / ".claude"
        alt_dir.mkdir()

        monkeypatch.setattr(
            "aec.lib.config.SUPPORTED_AGENTS",
            {
                "claude": {
                    "commands": ["claude"],
                    "alt_paths": [alt_dir],
                    "terminal_launch": True,
                    "launch_args": "--dangerously-skip-permissions",
                    "has_resume": True,
                    "resume_args": "--dangerously-skip-permissions --resume",
                },
            },
        )

        detected = detect_agents()
        assert "claude" in detected

    def test_does_not_detect_missing_agent(self, monkeypatch):
        """Should not detect agent when neither command nor alt_path exists."""
        def mock_which(cmd):
            return None

        monkeypatch.setattr("shutil.which", mock_which)
        monkeypatch.setattr(
            "aec.lib.config.SUPPORTED_AGENTS",
            {
                "gemini": {
                    "commands": ["gemini"],
                    "alt_paths": [],
                    "terminal_launch": True,
                    "launch_args": "--yolo",
                    "has_resume": True,
                    "resume_args": "--yolo --resume",
                },
            },
        )

        detected = detect_agents()
        assert "gemini" not in detected
        assert len(detected) == 0

    def test_returns_dict(self, monkeypatch):
        """detect_agents should always return a dict."""
        def mock_which(cmd):
            return None

        monkeypatch.setattr("shutil.which", mock_which)
        monkeypatch.setattr("aec.lib.config.SUPPORTED_AGENTS", {})

        result = detect_agents()
        assert isinstance(result, dict)

    def test_detects_multiple_agents(self, monkeypatch):
        """Should detect multiple agents when several are installed."""
        def mock_which(cmd):
            if cmd in ("claude", "cursor", "codex"):
                return f"/usr/local/bin/{cmd}"
            return None

        monkeypatch.setattr("shutil.which", mock_which)
        monkeypatch.setattr(
            "aec.lib.config.SUPPORTED_AGENTS",
            {
                "claude": SUPPORTED_AGENTS["claude"],
                "cursor": SUPPORTED_AGENTS["cursor"],
                "codex": SUPPORTED_AGENTS["codex"],
                "gemini": SUPPORTED_AGENTS["gemini"],
            },
        )

        detected = detect_agents()
        assert "claude" in detected
        assert "cursor" in detected
        assert "codex" in detected
        assert "gemini" not in detected


# ---------------------------------------------------------------------------
# Real detection integration test
# Verifies that detect_agents() finds agents actually installed on this machine.
# ---------------------------------------------------------------------------


class TestRealAgentDetection:
    """Integration test: verify detection against real installed agents.

    These tests run against the real system and confirm that detect_agents()
    correctly finds agents that are actually installed. They are skipped
    in CI via the 'integration' marker if needed.
    """

    @pytest.mark.parametrize("agent_name", list(EXPECTED_AGENT_NAMES))
    def test_installed_agent_is_detected(self, agent_name):
        """If an agent's command is on PATH, detect_agents() should find it."""
        agent_json = _REGISTRY["agents"][agent_name]
        commands = agent_json["commands"]

        # Check if the agent is actually installed
        installed = any(shutil.which(cmd) is not None for cmd in commands)

        if not installed:
            # Also check alt_paths from agents.json
            for alt in agent_json.get("alt_paths", []):
                expanded = Path(alt.replace("~", str(Path.home())))
                if expanded.exists():
                    installed = True
                    break

        if not installed:
            pytest.skip(f"{agent_name} not installed on this machine")

        detected = detect_agents()
        assert agent_name in detected, (
            f"{agent_name} is installed but detect_agents() did not find it"
        )

    def test_all_five_agents_detected_on_this_machine(self):
        """All 5 agents should be detected (skip if any is missing)."""
        detected = detect_agents()
        missing = EXPECTED_AGENT_NAMES - set(detected.keys())
        if missing:
            # Check if they're actually installed before failing
            truly_missing = set()
            for name in missing:
                agent_json = _REGISTRY["agents"][name]
                installed = any(
                    shutil.which(cmd) is not None
                    for cmd in agent_json["commands"]
                )
                if not installed:
                    for alt in agent_json.get("alt_paths", []):
                        expanded = Path(alt.replace("~", str(Path.home())))
                        if expanded.exists():
                            installed = True
                            break
                if installed:
                    truly_missing.add(name)

            if truly_missing:
                pytest.fail(
                    f"Agents installed but not detected: {truly_missing}"
                )
            else:
                pytest.skip(
                    f"Agents not installed on this machine: {missing}"
                )


# ---------------------------------------------------------------------------
# Integration: Raycast scripts to disk
# ---------------------------------------------------------------------------


class TestRaycastScriptGeneration:
    """Integration test: generate Raycast scripts to a temp directory."""

    def test_generate_and_write_scripts(self, tmp_path):
        """Should write executable scripts to disk."""
        from aec.commands.repo import _make_safe_name

        safe_name = _make_safe_name("My Project")
        assert safe_name == "my-project"

        config = SUPPORTED_AGENTS["claude"]

        # Write main script
        content = generate_raycast_script(
            "claude", config, "My Project", "/tmp/my-project"
        )
        script_path = tmp_path / f"claude-{safe_name}.sh"
        script_path.write_text(content)
        script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)

        assert script_path.exists()
        assert os.access(script_path, os.X_OK)
        assert "@raycast.title claude My Project" in script_path.read_text()

        # Write resume script
        resume_content = generate_raycast_script(
            "claude", config, "My Project", "/tmp/my-project", is_resume=True
        )
        resume_path = tmp_path / f"claude-{safe_name}-resume.sh"
        resume_path.write_text(resume_content)
        resume_path.chmod(resume_path.stat().st_mode | stat.S_IXUSR)

        assert resume_path.exists()
        assert "--resume" in resume_path.read_text()

    def test_all_agents_generate_valid_scripts(self, tmp_path):
        """Every agent should produce a valid Raycast script."""
        for name, config in SUPPORTED_AGENTS.items():
            content = generate_raycast_script(
                name, config, "test-proj", "/tmp/test-proj"
            )
            script_path = tmp_path / f"{name}-test-proj.sh"
            script_path.write_text(content)
            script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)

            assert script_path.exists()
            assert os.access(script_path, os.X_OK)
            text = script_path.read_text()
            assert "#!/bin/bash" in text
            assert "@raycast.schemaVersion 1" in text

            # Resume variants for agents that support it
            if config["has_resume"]:
                resume_content = generate_raycast_script(
                    name, config, "test-proj", "/tmp/test-proj", is_resume=True
                )
                resume_path = tmp_path / f"{name}-test-proj-resume.sh"
                resume_path.write_text(resume_content)
                assert "resume" in resume_path.read_text().lower()


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestMakeSafeName:
    """Test the _make_safe_name helper in repo.py."""

    def test_lowercase(self):
        from aec.commands.repo import _make_safe_name
        assert _make_safe_name("MyProject") == "myproject"

    def test_replaces_special_chars(self):
        from aec.commands.repo import _make_safe_name
        assert _make_safe_name("my_project.com") == "my-project-com"

    def test_collapses_multiple_hyphens(self):
        from aec.commands.repo import _make_safe_name
        assert _make_safe_name("my---project") == "my-project"

    def test_strips_leading_trailing_hyphens(self):
        from aec.commands.repo import _make_safe_name
        assert _make_safe_name("-my-project-") == "my-project"

    def test_already_safe(self):
        from aec.commands.repo import _make_safe_name
        assert _make_safe_name("my-project") == "my-project"

    def test_spaces_become_hyphens(self):
        from aec.commands.repo import _make_safe_name
        assert _make_safe_name("my project name") == "my-project-name"
