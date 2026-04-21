"""Tests for aec.lib.hooks.state — per-item hook state persistence."""

import pytest


class TestItemHookState:
    def test_fresh_load_returns_empty(self, tmp_path):
        from aec.lib.hooks.state import load_state
        state = load_state(tmp_path, item_type="skill", item_key="foo")
        assert state.hooks_installed == []
        assert state.hooks_skipped == []
        assert state.skipped_versions == []

    def test_round_trip(self, tmp_path):
        from aec.lib.hooks.state import load_state, save_state
        s = load_state(tmp_path, item_type="skill", item_key="foo")
        s.item_version = "1.0.0"
        s.hooks_file_hash = "sha256:abc"
        s.hooks_installed = [{
            "hook_id": "h1", "agent": "claude",
            "target_json_pointer": "/hooks/PostToolUse/0",
            "content_fingerprint": "sha256:def", "version": "1.0.0",
        }]
        save_state(tmp_path, s)
        loaded = load_state(tmp_path, item_type="skill", item_key="foo")
        assert loaded.item_version == "1.0.0"
        assert loaded.hooks_installed[0]["hook_id"] == "h1"

    def test_parallel_writes_to_different_items_both_persist(self, tmp_path):
        from aec.lib.hooks.state import load_state, save_state
        for key in ("foo", "bar"):
            s = load_state(tmp_path, item_type="skill", item_key=key)
            s.item_version = "1.0.0"
            save_state(tmp_path, s)
        assert (tmp_path / ".aec/installed-hooks/skill.foo.json").exists()
        assert (tmp_path / ".aec/installed-hooks/skill.bar.json").exists()

    def test_skipped_version_is_recorded(self, tmp_path):
        from aec.lib.hooks.state import (
            is_version_skipped,
            load_state,
            mark_version_skipped,
            save_state,
        )
        s = load_state(tmp_path, item_type="skill", item_key="foo")
        mark_version_skipped(s, "2.0.0")
        save_state(tmp_path, s)
        reloaded = load_state(tmp_path, item_type="skill", item_key="foo")
        assert is_version_skipped(reloaded, "2.0.0") is True
        assert is_version_skipped(reloaded, "1.0.0") is False

    def test_remove_state_file(self, tmp_path):
        from aec.lib.hooks.state import load_state, remove_state, save_state
        s = load_state(tmp_path, item_type="skill", item_key="foo")
        s.item_version = "1.0.0"
        save_state(tmp_path, s)
        assert (tmp_path / ".aec/installed-hooks/skill.foo.json").exists()
        remove_state(tmp_path, item_type="skill", item_key="foo")
        assert not (tmp_path / ".aec/installed-hooks/skill.foo.json").exists()

    def test_list_all_installed_items(self, tmp_path):
        from aec.lib.hooks.state import list_installed_items, load_state, save_state
        for key in ("a", "b", "c"):
            s = load_state(tmp_path, item_type="skill", item_key=key)
            s.item_version = "1.0.0"
            save_state(tmp_path, s)
        items = list_installed_items(tmp_path)
        assert {(t, k) for t, k in items} == {("skill", "a"), ("skill", "b"), ("skill", "c")}

    def test_rejects_key_with_path_separator(self, tmp_path):
        from aec.lib.hooks.state import load_state
        with pytest.raises(ValueError):
            load_state(tmp_path, item_type="skill", item_key="foo/bar")

    def test_rejects_type_with_path_separator(self, tmp_path):
        from aec.lib.hooks.state import load_state
        with pytest.raises(ValueError):
            load_state(tmp_path, item_type="skill/evil", item_key="foo")

    def test_allow_custom_check_defaults_false(self, tmp_path):
        from aec.lib.hooks.state import load_state
        s = load_state(tmp_path, item_type="skill", item_key="foo")
        assert s.allow_custom_check is False

    def test_remove_missing_state_is_noop(self, tmp_path):
        from aec.lib.hooks.state import remove_state
        remove_state(tmp_path, item_type="skill", item_key="ghost")
