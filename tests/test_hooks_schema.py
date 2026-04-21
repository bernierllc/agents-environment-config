"""Tests for aec.lib.hooks.schema — HooksFile and load_hooks_file."""

import json

import pytest


class TestLoadHooksFile:
    def test_loads_minimal_hooks_file(self, tmp_path):
        from aec.lib.hooks.schema import load_hooks_file

        minimal = {
            "$schema": "https://bernierllc.io/schemas/aec-hooks-v1.json",
            "version": "1.0.0",
            "hooks": [],
        }
        path = tmp_path / "hooks.json"
        path.write_text(json.dumps(minimal))

        hf = load_hooks_file(path)

        assert hf.version == "1.0.0"
        assert hf.hooks == []
        assert hf.claude == []
        assert hf.cursor == []
        assert hf.gemini == []
        assert hf.git == []

    def test_loads_generic_hook_fields(self, tmp_path):
        from aec.lib.hooks.schema import load_hooks_file

        data = {
            "$schema": "https://bernierllc.io/schemas/aec-hooks-v1.json",
            "version": "1.2.0",
            "hooks": [{
                "id": "check",
                "event": "on_file_edit",
                "match": "**/*.py",
                "command": "aec run-script foo check.sh",
                "description": "Lint Python files",
                "blocking": False,
                "timeout_ms": 3000,
                "when": {"repo_has_any": ["pyproject.toml"]},
            }],
        }
        (tmp_path / "hooks.json").write_text(json.dumps(data))

        hf = load_hooks_file(tmp_path / "hooks.json")

        assert len(hf.hooks) == 1
        h = hf.hooks[0]
        assert h.id == "check"
        assert h.event == "on_file_edit"
        assert h.match == "**/*.py"
        assert h.command == "aec run-script foo check.sh"
        assert h.description == "Lint Python files"
        assert h.blocking is False
        assert h.timeout_ms == 3000
        assert h.when is not None
        assert h.when.repo_has_any == ["pyproject.toml"]

    def test_defaults_blocking_to_false(self, tmp_path):
        from aec.lib.hooks.schema import load_hooks_file

        data = {
            "$schema": "x",
            "version": "1.0.0",
            "hooks": [{
                "id": "x",
                "event": "on_file_edit",
                "command": "echo hi",
                "description": "d",
            }],
        }
        (tmp_path / "hooks.json").write_text(json.dumps(data))
        hf = load_hooks_file(tmp_path / "hooks.json")
        assert hf.hooks[0].blocking is False
        assert hf.hooks[0].timeout_ms == 5000

    def test_raises_on_missing_file(self, tmp_path):
        from aec.lib.hooks.schema import load_hooks_file

        with pytest.raises(FileNotFoundError):
            load_hooks_file(tmp_path / "missing.json")

    def test_raises_on_invalid_json(self, tmp_path):
        from aec.lib.hooks.schema import load_hooks_file, HooksSchemaError

        (tmp_path / "hooks.json").write_text("not json {")
        with pytest.raises(HooksSchemaError):
            load_hooks_file(tmp_path / "hooks.json")

    def test_loads_all_generic_events(self, tmp_path):
        from aec.lib.hooks.schema import load_hooks_file, GENERIC_EVENTS
        events = sorted(GENERIC_EVENTS)
        data = {
            "$schema": "x", "version": "1.0.0",
            "hooks": [
                {"id": f"h{i}", "event": ev, "command": "c", "description": "d"}
                for i, ev in enumerate(events)
            ],
        }
        (tmp_path / "hooks.json").write_text(json.dumps(data))
        hf = load_hooks_file(tmp_path / "hooks.json")
        assert {h.event for h in hf.hooks} == set(events)
