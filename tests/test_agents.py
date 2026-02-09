"""Tests for agent detection and Raycast script generation."""

import os
import stat
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from aec.lib.config import (
    SUPPORTED_AGENTS,
    detect_agents,
    generate_raycast_script,
)


class TestSupportedAgents:
    """Test the SUPPORTED_AGENTS configuration structure."""

    def test_all_expected_agents_present(self):
        """All five expected agents should be defined."""
        expected = {"claude", "cursor", "gemini", "qwen", "codex"}
        assert set(SUPPORTED_AGENTS.keys()) == expected

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

    def test_claude_has_resume(self):
        """Claude should have resume support."""
        assert SUPPORTED_AGENTS["claude"]["has_resume"] is True
        assert "resume_args" in SUPPORTED_AGENTS["claude"]

    def test_cursor_is_not_terminal_launch(self):
        """Cursor should use direct launch, not terminal."""
        assert SUPPORTED_AGENTS["cursor"]["terminal_launch"] is False
        assert "launch_template" in SUPPORTED_AGENTS["cursor"]

    def test_terminal_agents_have_launch_args(self):
        """Terminal-launched agents should have launch_args defined."""
        for name, config in SUPPORTED_AGENTS.items():
            if config["terminal_launch"]:
                assert "launch_args" in config, f"Agent '{name}' missing launch_args"

    def test_claude_has_correct_launch_args(self):
        """Claude launch args should include --dangerously-skip-permissions."""
        assert "--dangerously-skip-permissions" in SUPPORTED_AGENTS["claude"]["launch_args"]
        assert "--dangerously-skip-permissions" in SUPPORTED_AGENTS["claude"]["resume_args"]
        assert "--resume" in SUPPORTED_AGENTS["claude"]["resume_args"]

    def test_no_resume_for_non_claude_agents(self):
        """Only claude should have has_resume=True."""
        for name, config in SUPPORTED_AGENTS.items():
            if name != "claude":
                assert config["has_resume"] is False, f"Agent '{name}' unexpectedly has resume"


class TestDetectAgents:
    """Test agent detection logic."""

    def test_detects_agent_via_command(self, monkeypatch):
        """Should detect agent when its command is on PATH."""
        def mock_which(cmd):
            if cmd == "claude":
                return "/usr/local/bin/claude"
            return None

        monkeypatch.setattr("shutil.which", mock_which)
        # Ensure alt_paths don't match
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
                    "launch_args": "",
                    "has_resume": False,
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
                "claude": {
                    "commands": ["claude"],
                    "alt_paths": [],
                    "terminal_launch": True,
                    "launch_args": "--dangerously-skip-permissions",
                    "has_resume": True,
                    "resume_args": "--dangerously-skip-permissions --resume",
                },
                "cursor": {
                    "commands": ["cursor"],
                    "alt_paths": [],
                    "terminal_launch": False,
                    "launch_template": "cursor {path}/",
                    "has_resume": False,
                },
                "codex": {
                    "commands": ["codex"],
                    "alt_paths": [],
                    "terminal_launch": True,
                    "launch_args": "",
                    "has_resume": False,
                },
                "gemini": {
                    "commands": ["gemini"],
                    "alt_paths": [],
                    "terminal_launch": True,
                    "launch_args": "",
                    "has_resume": False,
                },
            },
        )

        detected = detect_agents()
        assert "claude" in detected
        assert "cursor" in detected
        assert "codex" in detected
        assert "gemini" not in detected


class TestGenerateRaycastScript:
    """Test Raycast script content generation."""

    def _claude_config(self):
        return {
            "commands": ["claude"],
            "alt_paths": [],
            "terminal_launch": True,
            "launch_args": "--dangerously-skip-permissions",
            "has_resume": True,
            "resume_args": "--dangerously-skip-permissions --resume",
        }

    def _cursor_config(self):
        return {
            "commands": ["cursor"],
            "alt_paths": [],
            "terminal_launch": False,
            "launch_template": "cursor {path}/",
            "has_resume": False,
        }

    def _gemini_config(self):
        return {
            "commands": ["gemini"],
            "alt_paths": [],
            "terminal_launch": True,
            "launch_args": "",
            "has_resume": False,
        }

    def test_claude_script_has_raycast_metadata(self):
        """Claude script should contain Raycast metadata comments."""
        content = generate_raycast_script(
            "claude", self._claude_config(), "my-project", "/home/user/projects/my-project"
        )
        assert "#!/bin/bash" in content
        assert "@raycast.schemaVersion 1" in content
        assert "@raycast.title claude my-project" in content
        assert "@raycast.mode compact" in content
        assert "@raycast.description open claude my-project project" in content
        assert "@raycast.author matt_bernier" in content

    def test_claude_script_uses_terminal_launch(self):
        """Claude script should use osascript Terminal launch."""
        content = generate_raycast_script(
            "claude", self._claude_config(), "my-project", "/home/user/projects/my-project"
        )
        assert "osascript -e" in content
        assert 'tell application "Terminal"' in content
        assert "cd /home/user/projects/my-project/" in content
        assert "claude --dangerously-skip-permissions" in content

    def test_claude_resume_script(self):
        """Claude resume script should include --resume flag."""
        content = generate_raycast_script(
            "claude", self._claude_config(), "my-project", "/home/user/projects/my-project",
            is_resume=True,
        )
        assert "@raycast.title claude my-project resume" in content
        assert "@raycast.description open claude my-project project resume" in content
        assert "--dangerously-skip-permissions --resume" in content

    def test_cursor_script_uses_direct_launch(self):
        """Cursor script should use direct cursor command, not Terminal."""
        content = generate_raycast_script(
            "cursor", self._cursor_config(), "my-project", "/home/user/projects/my-project"
        )
        assert "cursor /home/user/projects/my-project/" in content
        assert "osascript" not in content
        assert "Terminal" not in content

    def test_gemini_script_uses_terminal_launch(self):
        """Gemini script should use Terminal launch like claude but without extra args."""
        content = generate_raycast_script(
            "gemini", self._gemini_config(), "my-project", "/home/user/projects/my-project"
        )
        assert "osascript -e" in content
        assert 'tell application "Terminal"' in content
        assert "cd /home/user/projects/my-project/; gemini" in content

    def test_script_starts_with_shebang(self):
        """Generated scripts must start with bash shebang."""
        for agent_name, config in [
            ("claude", self._claude_config()),
            ("cursor", self._cursor_config()),
            ("gemini", self._gemini_config()),
        ]:
            content = generate_raycast_script(
                agent_name, config, "test", "/tmp/test"
            )
            assert content.startswith("#!/bin/bash"), f"{agent_name} missing shebang"

    def test_project_name_in_title(self):
        """Project name should appear in the raycast title."""
        content = generate_raycast_script(
            "claude", self._claude_config(), "fancy-project", "/tmp/fancy-project"
        )
        assert "@raycast.title claude fancy-project" in content

    def test_project_path_in_command(self):
        """Absolute project path should appear in the launch command."""
        path = "/Users/dev/projects/my-app"
        content = generate_raycast_script(
            "claude", self._claude_config(), "my-app", path
        )
        assert path in content


class TestRaycastScriptGeneration:
    """Integration test: generate Raycast scripts to a temp directory."""

    def test_generate_and_write_scripts(self, tmp_path):
        """Should write executable scripts to disk."""
        from aec.commands.repo import _make_safe_name

        safe_name = _make_safe_name("My Project")
        assert safe_name == "my-project"

        config = {
            "commands": ["claude"],
            "alt_paths": [],
            "terminal_launch": True,
            "launch_args": "--dangerously-skip-permissions",
            "has_resume": True,
            "resume_args": "--dangerously-skip-permissions --resume",
        }

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
