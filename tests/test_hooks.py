"""Tests for aec.lib.hooks module."""

import json
from pathlib import Path

import pytest


class TestLanguageHooksRegistry:
    """Test the LANGUAGE_HOOKS registry is well-formed."""

    def test_registry_has_five_languages(self):
        """Registry should contain typescript, rust, python, go, ruby."""
        from aec.lib.hooks import LANGUAGE_HOOKS

        expected = {"typescript", "rust", "python", "go", "ruby"}
        assert set(LANGUAGE_HOOKS.keys()) == expected

    def test_each_language_has_required_keys(self):
        """Each language must have display_name, detect_files, command."""
        from aec.lib.hooks import LANGUAGE_HOOKS

        for key, lang in LANGUAGE_HOOKS.items():
            assert "display_name" in lang, f"{key} missing display_name"
            assert "detect_files" in lang, f"{key} missing detect_files"
            assert "command" in lang, f"{key} missing command"
            assert isinstance(lang["detect_files"], list), f"{key} detect_files must be a list"
            assert len(lang["detect_files"]) > 0, f"{key} must have at least one detect_file"


class TestDetectLanguages:
    """Test detect_languages function."""

    def test_detects_typescript(self, temp_dir):
        """Should detect TypeScript when tsconfig.json exists."""
        (temp_dir / "tsconfig.json").write_text("{}")
        from aec.lib.hooks import detect_languages
        result = detect_languages(temp_dir)
        assert "typescript" in result

    def test_detects_rust(self, temp_dir):
        """Should detect Rust when Cargo.toml exists."""
        (temp_dir / "Cargo.toml").write_text("[package]")
        from aec.lib.hooks import detect_languages
        result = detect_languages(temp_dir)
        assert "rust" in result

    def test_detects_python(self, temp_dir):
        """Should detect Python when pyproject.toml exists."""
        (temp_dir / "pyproject.toml").write_text("[project]")
        from aec.lib.hooks import detect_languages
        result = detect_languages(temp_dir)
        assert "python" in result

    def test_detects_python_from_mypy_ini(self, temp_dir):
        """Should detect Python when mypy.ini exists."""
        (temp_dir / "mypy.ini").write_text("[mypy]")
        from aec.lib.hooks import detect_languages
        result = detect_languages(temp_dir)
        assert "python" in result

    def test_detects_go(self, temp_dir):
        """Should detect Go when go.mod exists."""
        (temp_dir / "go.mod").write_text("module example.com/foo")
        from aec.lib.hooks import detect_languages
        result = detect_languages(temp_dir)
        assert "go" in result

    def test_detects_ruby(self, temp_dir):
        """Should detect Ruby when Gemfile exists."""
        (temp_dir / "Gemfile").write_text('source "https://rubygems.org"')
        from aec.lib.hooks import detect_languages
        result = detect_languages(temp_dir)
        assert "ruby" in result

    def test_detects_multiple_languages(self, temp_dir):
        """Should detect multiple languages in a monorepo."""
        (temp_dir / "tsconfig.json").write_text("{}")
        (temp_dir / "pyproject.toml").write_text("[project]")
        from aec.lib.hooks import detect_languages
        result = detect_languages(temp_dir)
        assert "typescript" in result
        assert "python" in result
        assert len(result) == 2

    def test_returns_empty_when_no_languages(self, temp_dir):
        """Should return empty list when no language files found."""
        from aec.lib.hooks import detect_languages
        result = detect_languages(temp_dir)
        assert result == []

    def test_returns_list_of_language_keys(self, temp_dir):
        """Return type should be a list of string keys."""
        (temp_dir / "Cargo.toml").write_text("[package]")
        from aec.lib.hooks import detect_languages
        result = detect_languages(temp_dir)
        assert isinstance(result, list)
        assert all(isinstance(k, str) for k in result)


class TestAgentHookConfigsRegistry:
    """Test the AGENT_HOOK_CONFIGS registry is well-formed."""

    def test_registry_has_three_agents(self):
        """Registry should contain claude, gemini, cursor."""
        from aec.lib.hooks import AGENT_HOOK_CONFIGS
        expected = {"claude", "gemini", "cursor"}
        assert set(AGENT_HOOK_CONFIGS.keys()) == expected

    def test_each_agent_has_required_keys(self):
        """Each agent must have config_path, config_format, template."""
        from aec.lib.hooks import AGENT_HOOK_CONFIGS
        for key, agent in AGENT_HOOK_CONFIGS.items():
            assert "config_path" in agent, f"{key} missing config_path"
            assert "config_format" in agent, f"{key} missing config_format"
            assert "template" in agent, f"{key} missing template"
            assert callable(agent["template"]), f"{key} template must be callable"


class TestGenerateHookConfig:
    """Test generate_hook_config function."""

    def test_claude_single_command(self):
        """Should generate correct Claude PostToolUse config."""
        from aec.lib.hooks import generate_hook_config
        result = generate_hook_config("claude", ["npx tsc --noEmit --pretty 2>&1 | head -20"])
        assert "hooks" in result
        hooks = result["hooks"]["PostToolUse"]
        assert len(hooks) == 1
        assert hooks[0]["matcher"] == "Edit|Write"
        assert len(hooks[0]["hooks"]) == 1
        assert hooks[0]["hooks"][0]["type"] == "command"
        assert hooks[0]["hooks"][0]["command"] == "npx tsc --noEmit --pretty 2>&1 | head -20"

    def test_claude_multiple_commands(self):
        """Should compose multiple commands into single Claude config."""
        from aec.lib.hooks import generate_hook_config
        commands = ["npx tsc --noEmit --pretty 2>&1 | head -20", "mypy . 2>&1 | head -20"]
        result = generate_hook_config("claude", commands)
        hooks = result["hooks"]["PostToolUse"][0]["hooks"]
        assert len(hooks) == 2
        assert hooks[0]["command"] == commands[0]
        assert hooks[1]["command"] == commands[1]

    def test_gemini_single_command(self):
        """Should generate correct Gemini AfterTool config with enableHooks."""
        from aec.lib.hooks import generate_hook_config
        result = generate_hook_config("gemini", ["cargo check 2>&1 | head -20"])
        assert result["tools"]["enableHooks"] is True
        assert result["hooks"]["enabled"] is True
        after_tool = result["hooks"]["AfterTool"]
        assert len(after_tool) == 1
        assert after_tool[0]["matcher"] == "write_file|replace"
        assert after_tool[0]["hooks"][0]["type"] == "command"

    def test_gemini_multiple_commands(self):
        """Should compose multiple commands into single Gemini config."""
        from aec.lib.hooks import generate_hook_config
        commands = ["cargo check 2>&1 | head -20", "mypy . 2>&1 | head -20"]
        result = generate_hook_config("gemini", commands)
        hooks = result["hooks"]["AfterTool"][0]["hooks"]
        assert len(hooks) == 2

    def test_cursor_single_command(self):
        """Should generate correct Cursor afterFileEdit config."""
        from aec.lib.hooks import generate_hook_config
        result = generate_hook_config("cursor", ["npx tsc --noEmit --pretty 2>&1 | head -20"])
        assert result["version"] == 1
        after_edit = result["hooks"]["afterFileEdit"]
        assert len(after_edit) == 1
        assert after_edit[0]["command"] == "npx tsc --noEmit --pretty 2>&1 | head -20"

    def test_cursor_multiple_commands(self):
        """Should compose multiple commands into Cursor config."""
        from aec.lib.hooks import generate_hook_config
        commands = ["npx tsc --noEmit --pretty 2>&1 | head -20", "mypy . 2>&1 | head -20"]
        result = generate_hook_config("cursor", commands)
        after_edit = result["hooks"]["afterFileEdit"]
        assert len(after_edit) == 2

    def test_unknown_agent_raises(self):
        """Should raise KeyError for unsupported agent."""
        from aec.lib.hooks import generate_hook_config
        with pytest.raises(KeyError):
            generate_hook_config("codex", ["echo hello"])
