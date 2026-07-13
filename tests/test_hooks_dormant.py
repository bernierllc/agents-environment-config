"""Guard for installing a hook-bearing skill globally (hooks go dormant).

Global installs wire no hooks, so a skill that ships hooks loses that
functionality when installed globally. The guard warns / refuses / confirms.
"""

import json

from aec.lib.hooks.dormant import (
    GUARD_ALLOWED,
    GUARD_CONFIRM,
    GUARD_OK,
    GUARD_REFUSE,
    count_item_hooks,
    dormant_guard_status,
)


def _write_hooks(item_dir, n):
    item_dir.mkdir(parents=True, exist_ok=True)
    hooks = [
        {"id": f"h{i}", "event": "on_file_edit", "command": "echo x",
         "description": "d"}
        for i in range(n)
    ]
    (item_dir / "hooks.json").write_text(
        json.dumps({"$schema": "x", "version": "1.0.0", "hooks": hooks})
    )


class TestCountItemHooks:
    def test_zero_when_no_hooks_file(self, tmp_path):
        assert count_item_hooks(tmp_path) == 0

    def test_counts_declared_hooks(self, tmp_path):
        _write_hooks(tmp_path / "skill", 2)
        assert count_item_hooks(tmp_path / "skill") == 2

    def test_zero_on_malformed_file(self, tmp_path):
        (tmp_path / "hooks.json").write_text("{not json")
        assert count_item_hooks(tmp_path) == 0


class TestDormantGuardStatus:
    def test_ok_when_not_global(self):
        assert dormant_guard_status(
            is_global=False, hook_count=3, assume_yes=False, allow_dormant=False
        ) == GUARD_OK

    def test_ok_when_global_but_no_hooks(self):
        assert dormant_guard_status(
            is_global=True, hook_count=0, assume_yes=True, allow_dormant=False
        ) == GUARD_OK

    def test_confirm_when_global_interactive(self):
        assert dormant_guard_status(
            is_global=True, hook_count=1, assume_yes=False, allow_dormant=False
        ) == GUARD_CONFIRM

    def test_refuse_when_global_noninteractive_without_flag(self):
        assert dormant_guard_status(
            is_global=True, hook_count=1, assume_yes=True, allow_dormant=False
        ) == GUARD_REFUSE

    def test_allowed_when_global_noninteractive_with_flag(self):
        assert dormant_guard_status(
            is_global=True, hook_count=1, assume_yes=True, allow_dormant=True
        ) == GUARD_ALLOWED
