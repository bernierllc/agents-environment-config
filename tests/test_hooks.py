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


class TestWriteHookConfig:
    """Test write_hook_config function."""

    def test_creates_new_config_file(self, temp_dir):
        """Should create config file when it doesn't exist."""
        from aec.lib.hooks import write_hook_config
        result = write_hook_config(
            project_dir=temp_dir,
            agent_key="claude",
            commands=["npx tsc --noEmit --pretty 2>&1 | head -20"],
        )
        assert result == "created"
        config_path = temp_dir / ".claude" / "settings.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert "hooks" in data
        assert data["hooks"]["PostToolUse"][0]["matcher"] == "Edit|Write"

    def test_creates_parent_directories(self, temp_dir):
        """Should create parent dirs (.claude/, .gemini/, etc.) if missing."""
        from aec.lib.hooks import write_hook_config
        write_hook_config(temp_dir, "gemini", ["cargo check 2>&1 | head -20"])
        config_path = temp_dir / ".gemini" / "settings.json"
        assert config_path.exists()

    def test_creates_cursor_hooks_json(self, temp_dir):
        """Should create .cursor/hooks.json for cursor."""
        from aec.lib.hooks import write_hook_config
        write_hook_config(temp_dir, "cursor", ["npx tsc --noEmit --pretty 2>&1 | head -20"])
        config_path = temp_dir / ".cursor" / "hooks.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert data["version"] == 1


class TestMergeHookConfig:
    """Test merge behavior when config file already exists."""

    def test_merge_adds_hooks_to_existing(self, temp_dir):
        """Should add hooks section to existing config without removing other keys."""
        config_dir = temp_dir / ".claude"
        config_dir.mkdir()
        config_path = config_dir / "settings.json"
        config_path.write_text(json.dumps({"permissions": {"allow": ["Read"]}}))
        from aec.lib.hooks import write_hook_config
        result = write_hook_config(
            project_dir=temp_dir,
            agent_key="claude",
            commands=["npx tsc --noEmit --pretty 2>&1 | head -20"],
            mode="merge",
        )
        assert result == "merged"
        data = json.loads(config_path.read_text())
        assert data["permissions"]["allow"] == ["Read"]
        assert "hooks" in data

    def test_merge_replaces_existing_hooks(self, temp_dir):
        """Should replace existing hooks section when merging."""
        config_dir = temp_dir / ".claude"
        config_dir.mkdir()
        config_path = config_dir / "settings.json"
        config_path.write_text(json.dumps({
            "permissions": {"allow": ["Read"]},
            "hooks": {"PostToolUse": [{"matcher": "Bash", "hooks": []}]},
        }))
        from aec.lib.hooks import write_hook_config
        result = write_hook_config(
            project_dir=temp_dir,
            agent_key="claude",
            commands=["cargo check 2>&1 | head -20"],
            mode="merge",
        )
        assert result == "merged"
        data = json.loads(config_path.read_text())
        assert data["permissions"]["allow"] == ["Read"]
        assert data["hooks"]["PostToolUse"][0]["matcher"] == "Edit|Write"

    def test_skip_returns_skipped(self, temp_dir):
        """Should return 'skipped' and not modify file when mode is skip."""
        config_dir = temp_dir / ".claude"
        config_dir.mkdir()
        config_path = config_dir / "settings.json"
        original = json.dumps({"existing": True})
        config_path.write_text(original)
        from aec.lib.hooks import write_hook_config
        result = write_hook_config(
            project_dir=temp_dir,
            agent_key="claude",
            commands=["npx tsc --noEmit --pretty 2>&1 | head -20"],
            mode="skip",
        )
        assert result == "skipped"
        assert config_path.read_text() == original

    def test_show_returns_config_without_writing(self, temp_dir):
        """Should return 'show' and not modify file when mode is show."""
        config_dir = temp_dir / ".claude"
        config_dir.mkdir()
        config_path = config_dir / "settings.json"
        original = json.dumps({"existing": True})
        config_path.write_text(original)
        from aec.lib.hooks import write_hook_config
        result = write_hook_config(
            project_dir=temp_dir,
            agent_key="claude",
            commands=["npx tsc --noEmit --pretty 2>&1 | head -20"],
            mode="show",
        )
        assert result == "show"
        assert config_path.read_text() == original

    def test_default_mode_creates_when_missing(self, temp_dir):
        """Default mode should create file when it doesn't exist."""
        from aec.lib.hooks import write_hook_config
        result = write_hook_config(temp_dir, "claude", ["npx tsc --noEmit --pretty 2>&1 | head -20"])
        assert result == "created"

    def test_default_mode_skips_when_exists(self, temp_dir):
        """Default mode (no explicit mode) when file exists should return 'exists'."""
        config_dir = temp_dir / ".claude"
        config_dir.mkdir()
        (config_dir / "settings.json").write_text("{}")
        from aec.lib.hooks import write_hook_config
        result = write_hook_config(temp_dir, "claude", ["npx tsc --noEmit --pretty 2>&1 | head -20"])
        assert result == "exists"


class TestHookModePreference:
    """Test hook_mode setting in preferences."""

    def test_hook_mode_default_is_none(self, temp_dir, monkeypatch):
        """hook_mode should be None when not yet set."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        from aec.lib.preferences import get_setting
        assert get_setting("hook_mode") is None

    def test_set_hook_mode_per_repo(self, temp_dir, monkeypatch):
        """Should store 'per-repo' hook_mode."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)
        from aec.lib.preferences import set_setting, get_setting
        set_setting("hook_mode", "per-repo")
        assert get_setting("hook_mode") == "per-repo"

    def test_set_hook_mode_auto(self, temp_dir, monkeypatch):
        """Should store 'auto' hook_mode."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)
        from aec.lib.preferences import set_setting, get_setting
        set_setting("hook_mode", "auto")
        assert get_setting("hook_mode") == "auto"

    def test_set_hook_mode_never(self, temp_dir, monkeypatch):
        """Should store 'never' hook_mode."""
        monkeypatch.setattr("aec.lib.preferences.AEC_PREFERENCES", temp_dir / "preferences.json")
        monkeypatch.setattr("aec.lib.preferences.AEC_HOME", temp_dir)
        from aec.lib.preferences import set_setting, get_setting
        set_setting("hook_mode", "never")
        assert get_setting("hook_mode") == "never"


class TestAgentsJsonHookSupport:
    """Test that agents.json has supports_hooks field."""

    def test_all_agents_have_supports_hooks_field(self):
        """Every agent in agents.json should have a supports_hooks boolean."""
        from aec.lib.registry import invalidate_cache, load_agent_registry

        invalidate_cache()
        registry = load_agent_registry()
        for key, agent in registry["agents"].items():
            assert "supports_hooks" in agent, f"Agent '{key}' missing supports_hooks"
            assert isinstance(agent["supports_hooks"], bool), (
                f"Agent '{key}' supports_hooks must be bool"
            )

    def test_claude_supports_hooks(self):
        """Claude should support hooks."""
        from aec.lib.registry import invalidate_cache, load_agent_registry

        invalidate_cache()
        registry = load_agent_registry()
        assert registry["agents"]["claude"]["supports_hooks"] is True

    def test_gemini_supports_hooks(self):
        """Gemini should support hooks."""
        from aec.lib.registry import invalidate_cache, load_agent_registry

        invalidate_cache()
        registry = load_agent_registry()
        assert registry["agents"]["gemini"]["supports_hooks"] is True

    def test_cursor_supports_hooks(self):
        """Cursor should support hooks."""
        from aec.lib.registry import invalidate_cache, load_agent_registry

        invalidate_cache()
        registry = load_agent_registry()
        assert registry["agents"]["cursor"]["supports_hooks"] is True

    def test_codex_does_not_support_hooks(self):
        """Codex should not support hooks."""
        from aec.lib.registry import invalidate_cache, load_agent_registry

        invalidate_cache()
        registry = load_agent_registry()
        assert registry["agents"]["codex"]["supports_hooks"] is False

    def test_qwen_does_not_support_hooks(self):
        """Qwen should not support hooks."""
        from aec.lib.registry import invalidate_cache, load_agent_registry

        invalidate_cache()
        registry = load_agent_registry()
        assert registry["agents"]["qwen"]["supports_hooks"] is False
