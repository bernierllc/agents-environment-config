"""Tests for pure merge helpers in aec.lib.hooks.installer."""

from aec.lib.hooks.fingerprint import fingerprint_hook


class TestMergeClaudeEntries:
    def test_empty_config_adds_entry(self):
        from aec.lib.hooks.installer import _merge_claude_entries
        entry = {"event_key": "PostToolUse",
                 "payload": {"matcher": "Edit|Write", "hooks": [{"command": "c"}]}}
        result = _merge_claude_entries({}, [entry])
        assert result["hooks"]["PostToolUse"][0]["matcher"] == "Edit|Write"

    def test_idempotent_same_fingerprint(self):
        from aec.lib.hooks.installer import _merge_claude_entries
        entry = {"event_key": "PostToolUse",
                 "payload": {"matcher": "Edit|Write", "hooks": [{"command": "c"}]}}
        once = _merge_claude_entries({}, [entry])
        twice = _merge_claude_entries(once, [entry])
        assert len(twice["hooks"]["PostToolUse"]) == 1

    def test_multiple_entries_all_added_when_first_matches(self):
        from aec.lib.hooks.installer import _merge_claude_entries
        entry1 = {"event_key": "PostToolUse", "payload": {"matcher": "A", "hooks": []}}
        entry2 = {"event_key": "PostToolUse", "payload": {"matcher": "B", "hooks": []}}
        first = _merge_claude_entries({}, [entry1])
        combined = _merge_claude_entries(first, [entry1, entry2])
        assert len(combined["hooks"]["PostToolUse"]) == 2
        matchers = [h["matcher"] for h in combined["hooks"]["PostToolUse"]]
        assert "A" in matchers and "B" in matchers

    def test_different_event_keys_independent_arrays(self):
        from aec.lib.hooks.installer import _merge_claude_entries
        e1 = {"event_key": "PostToolUse", "payload": {"matcher": "A"}}
        e2 = {"event_key": "PreToolUse", "payload": {"matcher": "B"}}
        result = _merge_claude_entries({}, [e1, e2])
        assert "PostToolUse" in result["hooks"]
        assert "PreToolUse" in result["hooks"]


class TestMergeGeminiEntries:
    def test_adds_to_gemini_hooks(self):
        from aec.lib.hooks.installer import _merge_gemini_entries
        entry = {"event_key": "AfterTool",
                 "payload": {"matcher": "write_file", "hooks": [{"command": "c"}]}}
        result = _merge_gemini_entries({}, [entry])
        assert result["hooks"]["AfterTool"][0]["matcher"] == "write_file"


class TestMergeCursorEntries:
    def test_cursor_shape(self):
        from aec.lib.hooks.installer import _merge_cursor_entries
        entry = {"event_key": "afterFileEdit", "payload": {"command": "c"}}
        result = _merge_cursor_entries({}, [entry])
        assert result["hooks"]["afterFileEdit"][0]["command"] == "c"


class TestRemoveFromConfig:
    def test_remove_by_fingerprint_leaves_others(self):
        from aec.lib.hooks.installer import _remove_from_claude
        existing = {"hooks": {"PostToolUse": [
            {"matcher": "A"}, {"matcher": "B"},
        ]}}
        fp_a = fingerprint_hook({"matcher": "A"})
        result = _remove_from_claude(existing, "PostToolUse", fp_a)
        assert result["hooks"]["PostToolUse"] == [{"matcher": "B"}]

    def test_remove_empty_array_cleans_up_key(self):
        from aec.lib.hooks.installer import _remove_from_claude
        existing = {"hooks": {"PostToolUse": [{"matcher": "A"}]}}
        fp_a = fingerprint_hook({"matcher": "A"})
        result = _remove_from_claude(existing, "PostToolUse", fp_a)
        assert "PostToolUse" not in result.get("hooks", {})
