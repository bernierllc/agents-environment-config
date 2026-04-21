"""Tests for aec.lib.hooks.validator — spec §1.6 rules."""

import pytest

from aec.lib.hooks.schema import (
    HooksFile, GenericHook, AgentOverride, WhenPredicate, load_hooks_file,
)

FIX = lambda name: f"tests/fixtures/hooks/{name}"


class TestValidateHooksFile:
    def _make(self, **overrides):
        return HooksFile(version="1.0.0", hooks=[], **overrides)

    def test_valid_minimal_file_has_no_errors(self):
        from aec.lib.hooks.validator import validate_hooks_file
        errs, _ = validate_hooks_file(self._make(), expected_version="1.0.0")
        assert errs == []

    def test_version_mismatch_is_error(self):
        from aec.lib.hooks.validator import validate_hooks_file
        errs, _ = validate_hooks_file(self._make(), expected_version="2.0.0")
        assert any("version" in e.message.lower() for e in errs)

    def test_duplicate_ids_fixture(self):
        from aec.lib.hooks.validator import validate_hooks_file
        hf = load_hooks_file(FIX("invalid_duplicate_ids.json"))
        errs, _ = validate_hooks_file(hf, expected_version="1.0.0")
        assert any("duplicate id" in e.message.lower() for e in errs)

    def test_unknown_event_fixture(self):
        from aec.lib.hooks.validator import validate_hooks_file
        hf = load_hooks_file(FIX("invalid_unknown_event.json"))
        errs, _ = validate_hooks_file(hf, expected_version="1.0.0")
        assert any("event" in e.message.lower() for e in errs)

    def test_empty_command_fixture(self):
        from aec.lib.hooks.validator import validate_hooks_file
        hf = load_hooks_file(FIX("invalid_empty_command.json"))
        errs, _ = validate_hooks_file(hf, expected_version="1.0.0")
        assert any("command" in e.message.lower() for e in errs)

    def test_custom_check_newline_fixture(self):
        from aec.lib.hooks.validator import validate_hooks_file
        hf = load_hooks_file(FIX("invalid_custom_check_newline.json"))
        errs, _ = validate_hooks_file(hf, expected_version="1.0.0")
        assert any("newline" in e.message.lower() for e in errs)

    def test_unknown_git_hook_fixture(self):
        from aec.lib.hooks.validator import validate_hooks_file
        hf = load_hooks_file(FIX("invalid_unknown_git_hook.json"))
        errs, _ = validate_hooks_file(hf, expected_version="1.0.0")
        assert any("git hook" in e.message.lower() for e in errs)

    def test_agent_override_mirroring_generic_is_warning(self):
        from aec.lib.hooks.validator import validate_hooks_file
        override = AgentOverride(
            agent="claude",
            payload={"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "echo"}]},
            id="mirror",
        )
        hf = HooksFile(version="1.0.0", claude=[override])
        errs, warns = validate_hooks_file(hf, expected_version="1.0.0")
        assert errs == []
        assert any("generic" in w.message.lower() for w in warns)

    def test_validator_does_not_check_script_existence(self, tmp_path):
        from aec.lib.hooks.validator import validate_hooks_file
        h = GenericHook(
            id="x", event="on_file_edit",
            command="aec run-script some-skill missing-script.sh",
            description="d",
        )
        hf = HooksFile(version="1.0.0", hooks=[h])
        errs, _ = validate_hooks_file(hf, expected_version="1.0.0")
        assert errs == []

    def test_duplicate_across_generic_and_override_is_error(self):
        from aec.lib.hooks.validator import validate_hooks_file
        h = GenericHook(id="shared", event="on_file_edit", command="c", description="d")
        override = AgentOverride(agent="claude", payload={"matcher": "X"}, id="shared")
        hf = HooksFile(version="1.0.0", hooks=[h], claude=[override])
        errs, _ = validate_hooks_file(hf, expected_version="1.0.0")
        assert any("duplicate id" in e.message.lower() for e in errs)
