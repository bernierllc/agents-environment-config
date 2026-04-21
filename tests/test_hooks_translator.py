"""Tests for aec.lib.hooks.translator — spec §1.3 matrix + P1-D10 drop."""

import pytest

from aec.lib.hooks.schema import HooksFile, GenericHook, AgentOverride


SKIP_MATRIX = [
    ("on_file_edit", "git"),
    ("on_file_read", "cursor"), ("on_file_read", "git"),
    ("pre_tool_use", "cursor"), ("pre_tool_use", "git"),
    ("session_start", "cursor"), ("session_start", "git"),
    ("pre_commit", "claude"), ("pre_commit", "gemini"), ("pre_commit", "cursor"),
    ("pre_push", "claude"), ("pre_push", "gemini"), ("pre_push", "cursor"),
]


@pytest.mark.parametrize("event,agent", SKIP_MATRIX)
def test_skip_matrix(event, agent):
    from aec.lib.hooks.translator import translate_to_agent
    h = GenericHook(id="x", event=event, command="c", description="d")
    hf = HooksFile(version="1.0.0", hooks=[h])
    assert translate_to_agent(hf, agent, resolved_commands={"x": "c"}) == []


class TestTranslateClaude:
    def test_on_file_edit_maps_to_PostToolUse(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="x", event="on_file_edit", command="echo hi",
                        description="d", match="**/*.py")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "claude", resolved_commands={"x": "echo hi"})
        assert len(entries) == 1
        e = entries[0]
        assert e["event_key"] == "PostToolUse"
        assert e["payload"]["matcher"] == "Edit|Write|MultiEdit"
        assert e["payload"]["hooks"][0]["command"] == "echo hi"
        assert e["source_hook_id"] == "x"
        assert "match" not in e["payload"]
        assert "match" not in e["payload"]["hooks"][0]
        assert h.match == "**/*.py"

    def test_on_file_read_maps_to_PostToolUse_Read(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="r", event="on_file_read", command="c", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "claude", resolved_commands={"r": "c"})
        assert entries[0]["event_key"] == "PostToolUse"
        assert entries[0]["payload"]["matcher"] == "Read"

    def test_pre_tool_use_maps_to_PreToolUse_without_matcher(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="p", event="pre_tool_use", command="c", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "claude", resolved_commands={"p": "c"})
        assert entries[0]["event_key"] == "PreToolUse"
        assert "matcher" not in entries[0]["payload"]

    def test_session_start_maps_to_SessionStart(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="s", event="session_start", command="c", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "claude", resolved_commands={"s": "c"})
        assert entries[0]["event_key"] == "SessionStart"


class TestTranslateGemini:
    def test_on_file_edit_maps_to_AfterTool(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="x", event="on_file_edit", command="c", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "gemini", resolved_commands={"x": "c"})
        assert entries[0]["event_key"] == "AfterTool"
        assert entries[0]["payload"]["matcher"] == "write_file|replace"

    def test_on_file_read_maps_to_AfterTool_read(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="r", event="on_file_read", command="c", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "gemini", resolved_commands={"r": "c"})
        assert entries[0]["event_key"] == "AfterTool"
        assert entries[0]["payload"]["matcher"] == "read_file"

    def test_pre_tool_use_maps_to_BeforeTool(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="p", event="pre_tool_use", command="c", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "gemini", resolved_commands={"p": "c"})
        assert entries[0]["event_key"] == "BeforeTool"

    def test_session_start_maps_to_SessionStart(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="s", event="session_start", command="c", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "gemini", resolved_commands={"s": "c"})
        assert entries[0]["event_key"] == "SessionStart"


class TestTranslateCursor:
    def test_on_file_edit_maps_to_afterFileEdit(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="x", event="on_file_edit", command="c", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "cursor", resolved_commands={"x": "c"})
        assert entries[0]["event_key"] == "afterFileEdit"


class TestTranslateGit:
    def test_pre_commit_maps_to_pre_commit_hook(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="x", event="pre_commit", command="lint.sh", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "git", resolved_commands={"x": "lint.sh"})
        assert entries[0]["event_key"] == "pre-commit"
        assert entries[0]["payload"]["command"] == "lint.sh"

    def test_pre_push_maps_to_pre_push_hook(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="x", event="pre_push", command="checks.sh", description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(hf, "git", resolved_commands={"x": "checks.sh"})
        assert entries[0]["event_key"] == "pre-push"


class TestOverridesPassThroughVerbatim:
    def test_claude_override_shape_unchanged(self):
        from aec.lib.hooks.translator import translate_to_agent
        override = AgentOverride(
            agent="claude",
            id="custom",
            payload={"matcher": "SubagentStop", "hooks": [{"command": "x"}]},
        )
        hf = HooksFile(version="1.0.0", claude=[override])
        entries = translate_to_agent(hf, "claude", resolved_commands={})
        assert entries[-1]["payload"]["matcher"] == "SubagentStop"
        assert entries[-1]["source_hook_id"] == "custom"

    def test_git_override_shape_unchanged(self):
        from aec.lib.hooks.translator import translate_to_agent
        override = AgentOverride(
            agent="git",
            id="custom-git",
            payload={"hook_name": "pre-commit", "command": "custom.sh"},
        )
        hf = HooksFile(version="1.0.0", git=[override])
        entries = translate_to_agent(hf, "git", resolved_commands={})
        assert entries[-1]["event_key"] == "pre-commit"
        assert entries[-1]["payload"]["command"] == "custom.sh"
        assert entries[-1]["source_hook_id"] == "custom-git"


class TestResolvedCommandSubstitution:
    def test_uses_resolved_command_if_present(self):
        from aec.lib.hooks.translator import translate_to_agent
        h = GenericHook(id="x", event="on_file_edit",
                        command="aec run-script fixture demo.sh",
                        description="d")
        hf = HooksFile(version="1.0.0", hooks=[h])
        entries = translate_to_agent(
            hf, "claude",
            resolved_commands={"x": "/abs/path/to/demo.sh"},
        )
        assert entries[0]["payload"]["hooks"][0]["command"] == "/abs/path/to/demo.sh"
