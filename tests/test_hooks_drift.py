"""Tests for aec.lib.hooks.drift — fingerprint-based reconciliation between
recorded hook state and the actual agent settings files.

The whole point: the recorded pointer (index) is a cache, the content
fingerprint is identity. When another tool inserts/removes entries the index
shifts but the hook is still present — verify must find it by fingerprint.
"""

import os
import json
from pathlib import Path


def _install_one_claude_hook(tmp_path: Path) -> Path:
    """Install a single claude hook the normal way, return repo_root."""
    from aec.lib.hooks.installer import install_item_hooks

    item_dir = tmp_path / "item"
    item_dir.mkdir(parents=True, exist_ok=True)
    (item_dir / "hooks.json").write_text(json.dumps({
        "$schema": "x", "version": "1.0.0", "hooks": [{
            "id": "lint", "event": "on_file_edit",
            "command": "echo hi", "description": "lint",
        }],
    }))
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    install_item_hooks(
        item_type="skill", item_key="demo", item_version="1.0.0",
        item_dir=item_dir, repo_root=repo_root, agents=["claude"],
    )
    return repo_root


class TestClassifyHook:
    def test_ok_when_present(self, tmp_path):
        from aec.lib.hooks.drift import Drift, classify_hook
        from aec.lib.hooks.state import load_state

        repo_root = _install_one_claude_hook(tmp_path)
        st = load_state(repo_root, item_type="skill", item_key="demo")
        result = classify_hook(
            repo_root, st.hooks_installed[0],
            item_type="skill", item_key="demo",
        )
        assert result.status is Drift.OK
        assert result.found_index == 0

    def test_missing_when_entry_clobbered(self, tmp_path):
        # Simulate an out-of-band edit that drops AEC's entry but leaves state.
        from aec.lib.hooks.drift import Drift, classify_hook
        from aec.lib.hooks.state import load_state

        repo_root = _install_one_claude_hook(tmp_path)
        settings_path = repo_root / ".claude/settings.json"
        settings_path.write_text(json.dumps({"hooks": {}}))

        st = load_state(repo_root, item_type="skill", item_key="demo")
        result = classify_hook(
            repo_root, st.hooks_installed[0],
            item_type="skill", item_key="demo",
        )
        assert result.status is Drift.MISSING
        assert result.found_index is None

    def test_missing_when_settings_file_absent(self, tmp_path):
        from aec.lib.hooks.drift import Drift, classify_hook
        from aec.lib.hooks.state import load_state

        repo_root = _install_one_claude_hook(tmp_path)
        (repo_root / ".claude/settings.json").unlink()

        st = load_state(repo_root, item_type="skill", item_key="demo")
        result = classify_hook(
            repo_root, st.hooks_installed[0],
            item_type="skill", item_key="demo",
        )
        assert result.status is Drift.MISSING

    def test_ok_after_index_shift(self, tmp_path):
        # Another tool prepends an unrelated entry; our index moves 0 -> 1.
        # Fingerprint still matches, so this is OK, not MISSING.
        from aec.lib.hooks.drift import Drift, classify_hook
        from aec.lib.hooks.state import load_state

        repo_root = _install_one_claude_hook(tmp_path)
        settings_path = repo_root / ".claude/settings.json"
        data = json.loads(settings_path.read_text())
        data["hooks"]["PostToolUse"].insert(0, {
            "matcher": "Edit|Write",
            "hooks": [{"type": "command", "command": "npx tsc --noEmit"}],
        })
        settings_path.write_text(json.dumps(data))

        st = load_state(repo_root, item_type="skill", item_key="demo")
        result = classify_hook(
            repo_root, st.hooks_installed[0],
            item_type="skill", item_key="demo",
        )
        assert result.status is Drift.OK
        assert result.found_index == 1


class TestVerifyRepo:
    def test_reports_ok_for_healthy_repo(self, tmp_path):
        from aec.lib.hooks.drift import Drift, verify_repo

        repo_root = _install_one_claude_hook(tmp_path)
        statuses = verify_repo(repo_root)
        assert len(statuses) == 1
        assert statuses[0].item_key == "demo"
        assert statuses[0].hook_id == "lint"
        assert statuses[0].status is Drift.OK

    def test_reports_missing_after_clobber(self, tmp_path):
        from aec.lib.hooks.drift import Drift, verify_repo

        repo_root = _install_one_claude_hook(tmp_path)
        (repo_root / ".claude/settings.json").write_text(json.dumps({"hooks": {}}))

        statuses = verify_repo(repo_root)
        assert [s.status for s in statuses] == [Drift.MISSING]

    def test_empty_repo_reports_nothing(self, tmp_path):
        from aec.lib.hooks.drift import verify_repo

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        assert verify_repo(repo_root) == []


def _install_with_source(tmp_path):
    """Install a hook from a source dir that survives as the repo-local item
    dir (so repair has a hooks.json to re-wire from). Returns repo_root."""
    from aec.lib.hooks.installer import install_item_hooks

    repo_root = tmp_path / "repo"
    item_dir = repo_root / ".claude" / "skills" / "demo"
    item_dir.mkdir(parents=True, exist_ok=True)
    (item_dir / "hooks.json").write_text(json.dumps({
        "$schema": "x", "version": "1.0.0", "hooks": [{
            "id": "lint", "event": "on_file_edit",
            "command": "echo hi", "description": "lint",
        }],
    }))
    install_item_hooks(
        item_type="skill", item_key="demo", item_version="1.0.0",
        item_dir=item_dir, repo_root=repo_root, agents=["claude"],
    )
    return repo_root


def _add_second_item(repo_root, key):
    """Install another repo-local skill beside the one _install_with_source made."""
    from aec.lib.hooks.installer import install_item_hooks

    item_dir = repo_root / ".claude" / "skills" / key
    item_dir.mkdir(parents=True, exist_ok=True)
    (item_dir / "hooks.json").write_text(json.dumps({
        "$schema": "x", "version": "1.0.0", "hooks": [{
            "id": "fmt", "event": "on_file_edit",
            "command": "echo fmt", "description": "fmt",
        }],
    }))
    install_item_hooks(
        item_type="skill", item_key=key, item_version="1.0.0",
        item_dir=item_dir, repo_root=repo_root, agents=["claude"],
    )


class TestRepairRepo:
    def test_repair_restores_clobbered_hook(self, tmp_path):
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo

        repo_root = _install_with_source(tmp_path)
        (repo_root / ".claude/settings.json").write_text(json.dumps({"hooks": {}}))
        assert verify_repo(repo_root)[0].status is Drift.MISSING

        results = repair_repo(repo_root)

        assert any(r.repaired for r in results)
        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]
        settings = json.loads((repo_root / ".claude/settings.json").read_text())
        assert settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"] == "echo hi"

    def test_repair_healthy_repo_is_noop(self, tmp_path):
        from aec.lib.hooks.drift import repair_repo

        repo_root = _install_with_source(tmp_path)
        results = repair_repo(repo_root)
        assert all(not r.repaired for r in results)

    def test_repair_reports_unrepairable_when_source_gone(self, tmp_path):
        import shutil

        from aec.lib.hooks.drift import repair_repo

        repo_root = _install_with_source(tmp_path)
        (repo_root / ".claude/settings.json").write_text(json.dumps({"hooks": {}}))
        shutil.rmtree(repo_root / ".claude" / "skills" / "demo")

        results = repair_repo(repo_root)
        assert results and not any(r.repaired for r in results)
        assert any("source" in (r.detail or "").lower() for r in results)

    def test_one_broken_item_does_not_abort_the_rest(self, tmp_path):
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo

        repo_root = _install_with_source(tmp_path)
        _add_second_item(repo_root, "broken")
        (repo_root / ".claude/settings.json").write_text(json.dumps({"hooks": {}}))
        (repo_root / ".claude/skills/broken/hooks.json").write_text("{not json")

        results = {r.item_key: r for r in repair_repo(repo_root)}

        assert results["demo"].repaired
        assert not results["broken"].repaired and results["broken"].detail
        by_key = {s.item_key: s.status for s in verify_repo(repo_root)}
        assert by_key == {"demo": Drift.OK, "broken": Drift.MISSING}


class TestCoOwnedEntries:
    """Two items rendering the same payload share one deduped settings entry."""

    @staticmethod
    def _two_items_same_payload(tmp_path):
        from aec.lib.hooks.installer import install_item_hooks

        repo_root = tmp_path / "repo"
        for key in ("a", "b"):
            item_dir = repo_root / ".claude" / "skills" / key
            item_dir.mkdir(parents=True)
            (item_dir / "hooks.json").write_text(json.dumps({
                "$schema": "x", "version": "1.0.0", "hooks": [{
                    "id": "lint", "event": "on_file_edit",
                    "command": "echo same", "description": "d",
                }],
            }))
            install_item_hooks(
                item_type="skill", item_key=key, item_version="1.0.0",
                item_dir=item_dir, repo_root=repo_root, agents=["claude"],
            )
        return repo_root

    def test_repairing_one_owner_leaves_the_other_intact(self, tmp_path):
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo

        repo_root = self._two_items_same_payload(tmp_path)
        hooks_json = repo_root / ".claude/skills/a/hooks.json"
        data = json.loads(hooks_json.read_text())
        data["hooks"][0]["command"] = "echo changed"
        hooks_json.write_text(json.dumps(data))

        repair_repo(repo_root)
        assert {s.item_key: s.status for s in verify_repo(repo_root)} == {
            "a": Drift.OK, "b": Drift.OK}

    def test_uninstalling_one_owner_keeps_the_shared_entry(self, tmp_path):
        from aec.lib.hooks.drift import Drift, verify_repo
        from aec.lib.hooks.installer import remove_item_hooks

        repo_root = self._two_items_same_payload(tmp_path)
        remove_item_hooks(item_type="skill", item_key="a", repo_root=repo_root)
        assert [(s.item_key, s.status) for s in verify_repo(repo_root)] == [
            ("b", Drift.OK)]


class TestStaleAbsolutePaths:
    """Repos installed before the $CLAUDE_PROJECT_DIR rendering.

    Their settings.json holds this machine's absolute repo path. The hook still
    fires here, so it is not MISSING — but it breaks in a clone or worktree.
    `verify` must call it STALE and `--repair` must upgrade it in place without
    leaving the old absolute entry behind.
    """

    @staticmethod
    def _install_repo_local(tmp_path: Path) -> Path:
        from aec.lib.hooks.installer import install_item_hooks

        repo_root = tmp_path / "repo"
        item_dir = repo_root / ".claude" / "skills" / "demo"
        (item_dir / "scripts").mkdir(parents=True)
        script = item_dir / "scripts" / "check.sh"
        script.write_text("#!/bin/sh\necho ok\n")
        script.chmod(0o755)
        (item_dir / "hooks.json").write_text(json.dumps({
            "$schema": "x", "version": "1.0.0", "hooks": [{
                "id": "lint", "event": "on_file_edit",
                "command": "aec run-script skill:demo check.sh",
                "description": "d",
            }],
        }))
        install_item_hooks(
            item_type="skill", item_key="demo", item_version="1.0.0",
            item_dir=item_dir, repo_root=repo_root, agents=["claude"],
        )
        return repo_root

    @staticmethod
    def _downgrade_to_absolute(repo_root: Path) -> None:
        """Rewrite settings + state the way a pre-fix install left them."""
        from aec.lib.hooks.fingerprint import fingerprint_hook
        from aec.lib.hooks.state import load_state, save_state

        settings_path = repo_root / ".claude/settings.json"
        settings = json.loads(settings_path.read_text())
        entry = settings["hooks"]["PostToolUse"][0]
        inner = entry["hooks"][0]
        inner["command"] = inner["command"].replace(
            '"$CLAUDE_PROJECT_DIR"/', f"{repo_root}/"
        )
        assert str(repo_root) in inner["command"]
        settings_path.write_text(json.dumps(settings))

        st = load_state(repo_root, item_type="skill", item_key="demo")
        st.hooks_installed[0]["content_fingerprint"] = fingerprint_hook(entry)
        save_state(repo_root, st)

    def test_absolute_path_reports_stale(self, tmp_path):
        from aec.lib.hooks.drift import Drift, verify_repo

        repo_root = self._install_repo_local(tmp_path)
        self._downgrade_to_absolute(repo_root)

        statuses = verify_repo(repo_root)
        assert [s.status for s in statuses] == [Drift.STALE]

    def test_repair_upgrades_and_leaves_no_duplicate(self, tmp_path):
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo

        repo_root = self._install_repo_local(tmp_path)
        self._downgrade_to_absolute(repo_root)

        assert any(r.repaired for r in repair_repo(repo_root))

        settings = json.loads((repo_root / ".claude/settings.json").read_text())
        arr = settings["hooks"]["PostToolUse"]
        assert len(arr) == 1, "the stale absolute entry must be retracted"
        cmd = arr[0]["hooks"][0]["command"]
        assert '"$CLAUDE_PROJECT_DIR"/' in cmd
        assert str(repo_root) not in cmd
        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]

    def test_portable_install_is_not_stale(self, tmp_path):
        from aec.lib.hooks.drift import Drift, verify_repo

        repo_root = self._install_repo_local(tmp_path)
        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]


class TestUnguardedScriptCommands:
    """A portable-but-unguarded command is STALE too.

    Rendering the path as `$CLAUDE_PROJECT_DIR` made settings.json portable,
    but the file it points at (`.claude/skills/**/scripts/*`) is usually
    untracked while settings.json is tracked. A clone therefore wires a hook
    to a file that isn't there and every matching edit exits 127. Repair has
    to upgrade those installs in place.
    """

    @staticmethod
    def _drop_guard(repo_root: Path) -> str:
        """Rewrite settings + state the way a pre-guard install left them."""
        from aec.lib.hooks.fingerprint import fingerprint_hook
        from aec.lib.hooks.state import load_state, save_state

        settings_path = repo_root / ".claude/settings.json"
        settings = json.loads(settings_path.read_text())
        entry = settings["hooks"]["PostToolUse"][0]
        inner = entry["hooks"][0]
        guarded = inner["command"]
        # "if [ -f P ]; then sh P args; fi" -> "P args" (pre-guard installs
        # also exec'd the path directly, with no interpreter in front).
        body = guarded.split("; then ", 1)[1].rsplit("; fi", 1)[0]
        body = body[body.index('"$CLAUDE_PROJECT_DIR"'):]
        inner["command"] = body
        settings_path.write_text(json.dumps(settings))

        st = load_state(repo_root, item_type="skill", item_key="demo")
        st.hooks_installed[0]["content_fingerprint"] = fingerprint_hook(entry)
        save_state(repo_root, st)
        return body

    def test_hand_written_command_is_not_stale(self, tmp_path):
        """A hooks.json command is installed verbatim, so it never differs.

        Neither mentioning `$CLAUDE_PROJECT_DIR` nor an `-x` guard on the
        item's own script makes it STALE — repair would rewrite it unchanged.
        """
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo
        from aec.lib.hooks.installer import install_item_hooks

        repo_root = tmp_path / "repo"
        item_dir = repo_root / ".claude" / "skills" / "demo"
        (item_dir / "scripts").mkdir(parents=True)
        own = ".claude/skills/demo/scripts/custom.sh"
        hooks = [
            {"id": "a", "event": "on_file_edit", "description": "d",
             "command": 'printf %s "$CLAUDE_PROJECT_DIR"'},
            {"id": "b", "event": "on_file_edit", "description": "d",
             "command": f"if [ -x {own} ]; then {own}; fi"},
        ]
        (item_dir / "hooks.json").write_text(json.dumps(
            {"$schema": "x", "version": "1.0.0", "hooks": hooks}))
        install_item_hooks(
            item_type="skill", item_key="demo", item_version="1.0.0",
            item_dir=item_dir, repo_root=repo_root, agents=["claude"],
        )

        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK] * 2
        assert not any(r.repaired for r in repair_repo(repo_root))

    def test_unguarded_project_dir_reports_stale(self, tmp_path):
        from aec.lib.hooks.drift import Drift, verify_repo

        repo_root = TestStaleAbsolutePaths._install_repo_local(tmp_path)
        body = self._drop_guard(repo_root)
        assert body.startswith('"$CLAUDE_PROJECT_DIR"/')

        assert [s.status for s in verify_repo(repo_root)] == [Drift.STALE]

    def test_repair_adds_the_guard(self, tmp_path):
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo
        from aec.lib.hooks.installer import is_guarded

        repo_root = TestStaleAbsolutePaths._install_repo_local(tmp_path)
        self._drop_guard(repo_root)

        assert any(r.repaired for r in repair_repo(repo_root))

        settings = json.loads(
            (repo_root / ".claude/settings.json").read_text()
        )
        arr = settings["hooks"]["PostToolUse"]
        assert len(arr) == 1, "the unguarded entry must be retracted"
        assert is_guarded(arr[0]["hooks"][0]["command"])
        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]

    def test_legacy_exec_bit_guard_reports_stale_and_repairs(self, tmp_path):
        """`if [ -x P ]; then P; fi` was the previous rendering.

        Git tracks +x itself, so a script committed at 0644 is non-executable
        in every clone and that guard kept the hook silently off. Repair must
        rewrite it to the interpreter rendering.
        """
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo

        repo_root = TestStaleAbsolutePaths._install_repo_local(tmp_path)
        body = self._drop_guard(repo_root)
        self._set_command(repo_root, f"if [ -x {body.split()[0]} ]; then {body}; fi")

        assert [s.status for s in verify_repo(repo_root)] == [Drift.STALE]
        assert any(r.repaired for r in repair_repo(repo_root))
        settings = json.loads(
            (repo_root / ".claude/settings.json").read_text()
        )
        arr = settings["hooks"]["PostToolUse"]
        assert len(arr) == 1
        assert arr[0]["hooks"][0]["command"].startswith("if [ -f ")
        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]

    @staticmethod
    def _set_command(repo_root: Path, command: str) -> None:
        from aec.lib.hooks.fingerprint import fingerprint_hook
        from aec.lib.hooks.state import load_state, save_state

        settings_path = repo_root / ".claude/settings.json"
        settings = json.loads(settings_path.read_text())
        entry = settings["hooks"]["PostToolUse"][0]
        entry["hooks"][0]["command"] = command
        settings_path.write_text(json.dumps(settings))
        st = load_state(repo_root, item_type="skill", item_key="demo")
        st.hooks_installed[0]["content_fingerprint"] = fingerprint_hook(entry)
        save_state(repo_root, st)

    def test_git_block_with_legacy_exec_bit_guard_is_stale(self, tmp_path):
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo
        from aec.lib.hooks.installer import install_item_hooks

        repo_root = tmp_path / "repo"
        (repo_root / ".git/hooks").mkdir(parents=True)
        item_dir = repo_root / ".claude" / "skills" / "demo"
        (item_dir / "scripts").mkdir(parents=True)
        (item_dir / "scripts" / "check.sh").write_text("#!/bin/sh\necho ok\n")
        (item_dir / "hooks.json").write_text(json.dumps({
            "$schema": "x", "version": "1.0.0", "hooks": [{
                "id": "lint", "event": "pre_commit",
                "command": "aec run-script skill:demo check.sh",
                "description": "d",
            }],
        }))
        install_item_hooks(
            item_type="skill", item_key="demo", item_version="1.0.0",
            item_dir=item_dir, repo_root=repo_root, agents=["git"],
        )
        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]

        hook = repo_root / ".git/hooks/pre-commit"
        rel = ".claude/skills/demo/scripts/check.sh"
        text = hook.read_text()
        new = f"if [ -f {rel} ]; then /bin/sh {rel}; fi"
        assert new in text
        hook.write_text(text.replace(new, f"if [ -x {rel} ]; then {rel}; fi"))
        assert [s.status for s in verify_repo(repo_root)] == [Drift.STALE]

        assert any(r.repaired for r in repair_repo(repo_root))
        assert new in hook.read_text()
        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]

    def test_gemini_direct_exec_is_stale_and_repairs(self, tmp_path):
        """gemini/cursor used to exec the bare path, which needs +x."""
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo
        from aec.lib.hooks.fingerprint import fingerprint_hook
        from aec.lib.hooks.installer import install_item_hooks
        from aec.lib.hooks.state import load_state, save_state

        repo_root = tmp_path / "repo"
        item_dir = repo_root / ".claude" / "skills" / "demo"
        (item_dir / "scripts").mkdir(parents=True)
        script = item_dir / "scripts" / "check.sh"
        script.write_text("#!/bin/sh\necho ok\n")
        (item_dir / "hooks.json").write_text(json.dumps({
            "$schema": "x", "version": "1.0.0", "hooks": [{
                "id": "lint", "event": "on_file_edit",
                "command": "aec run-script skill:demo check.sh",
                "description": "d",
            }],
        }))
        install_item_hooks(
            item_type="skill", item_key="demo", item_version="1.0.0",
            item_dir=item_dir, repo_root=repo_root, agents=["gemini"],
        )
        settings_path = repo_root / ".gemini/settings.json"
        settings = json.loads(settings_path.read_text())
        event = next(iter(settings["hooks"]))
        entry = settings["hooks"][event][0]
        current = json.dumps(entry)
        assert f"/bin/sh {script}" in current

        # What the pre-interpreter install wrote: the bare path.
        entry = json.loads(current.replace(f"/bin/sh {script}", str(script)))
        settings["hooks"][event] = [entry]
        settings_path.write_text(json.dumps(settings))
        st = load_state(repo_root, item_type="skill", item_key="demo")
        st.hooks_installed[0]["content_fingerprint"] = fingerprint_hook(entry)
        save_state(repo_root, st)

        assert [s.status for s in verify_repo(repo_root)] == [Drift.STALE]
        assert any(r.repaired for r in repair_repo(repo_root))
        arr = json.loads(settings_path.read_text())["hooks"][event]
        assert [json.dumps(e) for e in arr] == [current]
        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]

    def test_hook_moved_to_another_event_is_stale(self, tmp_path):
        """Same id and command, new event: the old block fires on the wrong op."""
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo
        from aec.lib.hooks.installer import install_item_hooks

        repo_root = tmp_path / "repo"
        (repo_root / ".git/hooks").mkdir(parents=True)
        item_dir = repo_root / ".claude" / "skills" / "demo"
        item_dir.mkdir(parents=True)

        def write(event):
            (item_dir / "hooks.json").write_text(json.dumps({
                "$schema": "x", "version": "1.0.0", "hooks": [{
                    "id": "lint", "event": event, "command": "true",
                    "description": "d",
                }],
            }))

        write("pre_commit")
        install_item_hooks(
            item_type="skill", item_key="demo", item_version="1.0.0",
            item_dir=item_dir, repo_root=repo_root, agents=["git"],
        )
        write("pre_push")
        assert [s.status for s in verify_repo(repo_root)] == [Drift.STALE]
        assert any(r.repaired for r in repair_repo(repo_root))
        assert "AEC:BEGIN" not in (repo_root / ".git/hooks/pre-commit").read_text()
        assert "AEC:BEGIN" in (repo_root / ".git/hooks/pre-push").read_text()
        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]

    def test_hook_removed_from_source_is_stale_and_repair_retracts_it(
        self, tmp_path
    ):
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo

        repo_root = TestStaleAbsolutePaths._install_repo_local(tmp_path)
        hooks_json = repo_root / ".claude/skills/demo/hooks.json"
        data = json.loads(hooks_json.read_text())
        data["hooks"][0]["id"] = "renamed"
        hooks_json.write_text(json.dumps(data))

        assert [s.status for s in verify_repo(repo_root)] == [Drift.STALE]
        assert any(r.repaired for r in repair_repo(repo_root))
        settings = json.loads((repo_root / ".claude/settings.json").read_text())
        assert len(settings["hooks"]["PostToolUse"]) == 1
        assert [(s.hook_id, s.status) for s in verify_repo(repo_root)] == [
            ("renamed", Drift.OK)]

    def test_hook_whose_when_turned_false_is_stale_and_retracted(self, tmp_path):
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo

        repo_root = TestStaleAbsolutePaths._install_repo_local(tmp_path)
        hooks_json = repo_root / ".claude/skills/demo/hooks.json"
        data = json.loads(hooks_json.read_text())
        data["hooks"][0]["when"] = {"repo_has": ["package.json"]}
        hooks_json.write_text(json.dumps(data))

        assert [s.status for s in verify_repo(repo_root)] == [Drift.STALE]
        assert any(r.repaired for r in repair_repo(repo_root))
        settings = json.loads((repo_root / ".claude/settings.json").read_text())
        assert not settings.get("hooks", {}).get("PostToolUse")
        assert verify_repo(repo_root) == []

    def test_skipped_hook_with_missing_script_does_not_blind_drift(self, tmp_path):
        """An inapplicable run-script hook may lack its script; the rest still counts."""
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo

        repo_root = TestStaleAbsolutePaths._install_repo_local(tmp_path)
        hooks_json = repo_root / ".claude/skills/demo/hooks.json"
        data = json.loads(hooks_json.read_text())
        data["hooks"][0]["when"] = {"repo_has": ["package.json"]}
        data["hooks"].append({
            "id": "other", "event": "on_file_edit", "description": "d",
            "command": "aec run-script skill:demo gone.sh",
            "when": {"repo_has": ["package.json"]},
        })
        hooks_json.write_text(json.dumps(data))

        assert [s.status for s in verify_repo(repo_root)] == [Drift.STALE]
        assert any(r.repaired for r in repair_repo(repo_root))
        assert verify_repo(repo_root) == []

    def test_verify_never_runs_custom_check(self, tmp_path):
        from aec.lib.hooks.drift import Drift, verify_repo

        repo_root = TestStaleAbsolutePaths._install_repo_local(tmp_path)
        hooks_json = repo_root / ".claude/skills/demo/hooks.json"
        data = json.loads(hooks_json.read_text())
        data["hooks"][0]["when"] = {"custom_check": "touch ran"}
        hooks_json.write_text(json.dumps(data))

        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]
        assert not (repo_root / "ran").exists()

        # Its file predicates still count.
        data["hooks"][0]["when"]["repo_has"] = ["package.json"]
        hooks_json.write_text(json.dumps(data))
        assert [s.status for s in verify_repo(repo_root)] == [Drift.STALE]
        assert not (repo_root / "ran").exists()

    def test_malformed_source_entry_does_not_crash_verify(self, tmp_path):
        from aec.lib.hooks.drift import Drift, verify_repo

        repo_root = TestStaleAbsolutePaths._install_repo_local(tmp_path)
        hooks_json = repo_root / ".claude/skills/demo/hooks.json"
        wrong_field = {"id": "lint", "event": "on_file_edit", "command": 42,
                       "description": "d"}
        for bad in ({"hooks": ["bad"]}, {"hooks": [], "claude": ["bad"]},
                    {"hooks": [wrong_field]},
                    {"hooks": [], "git": [{"id": "x", "hook_name": "pre-commit"}]},
                    {"hooks": [dict(wrong_field, command="true",
                                    when={"repo_has": [42]})]}):
            hooks_json.write_text(json.dumps({"version": "1.0.0", **bad}))
            assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]

    def test_command_containing_the_end_marker_is_read_whole(self, tmp_path):
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo
        from aec.lib.hooks.installer import install_item_hooks

        repo_root = tmp_path / "repo"
        (repo_root / ".git/hooks").mkdir(parents=True)
        item_dir = repo_root / ".claude" / "skills" / "demo"
        item_dir.mkdir(parents=True)
        (item_dir / "hooks.json").write_text(json.dumps({
            "$schema": "x", "version": "1.0.0", "hooks": [{
                "id": "lint", "event": "pre_commit",
                "command": "echo '# <<< AEC:END'", "description": "d",
            }],
        }))
        install_item_hooks(
            item_type="skill", item_key="demo", item_version="1.0.0",
            item_dir=item_dir, repo_root=repo_root, agents=["git"],
        )
        before = (repo_root / ".git/hooks/pre-commit").read_text()
        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]
        assert not any(r.repaired for r in repair_repo(repo_root))
        assert (repo_root / ".git/hooks/pre-commit").read_text() == before

    def test_command_with_the_end_marker_as_a_line_is_refused(self, tmp_path):
        import pytest
        from aec.lib.hooks.git_blocks import END_MARKER, write_block

        hook = tmp_path / "pre-commit"
        with pytest.raises(ValueError, match="AEC:END"):
            write_block(hook, item_key="skill:demo", hook_id="lint",
                        version="1", command=f"cat <<'X'\n{END_MARKER}\nX")
        assert not hook.exists()

    def test_repair_installs_an_item_updated_with_a_version_bump(self, tmp_path):
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo
        from aec.lib.hooks.state import load_state

        repo_root = TestStaleAbsolutePaths._install_repo_local(tmp_path)
        hooks_json = repo_root / ".claude/skills/demo/hooks.json"
        data = json.loads(hooks_json.read_text())
        data["version"] = "1.1.0"
        data["hooks"][0]["command"] += " --strict"
        hooks_json.write_text(json.dumps(data))

        assert [s.status for s in verify_repo(repo_root)] == [Drift.STALE]
        assert all(r.repaired for r in repair_repo(repo_root))
        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]
        st = load_state(repo_root, item_type="skill", item_key="demo")
        assert st.item_version == "1.1.0"

    def test_hand_written_exec_bit_guard_in_git_hook_is_not_stale(self, tmp_path):
        """A raw hooks.json command passes through verbatim; repair can't change it."""
        from aec.lib.hooks.drift import Drift, repair_repo, verify_repo
        from aec.lib.hooks.installer import install_item_hooks

        repo_root = tmp_path / "repo"
        (repo_root / ".git/hooks").mkdir(parents=True)
        item_dir = repo_root / ".claude" / "skills" / "demo"
        item_dir.mkdir(parents=True)
        (item_dir / "hooks.json").write_text(json.dumps({
            "$schema": "x", "version": "1.0.0", "hooks": [{
                "id": "lint", "event": "pre_commit",
                "command": "if [ -x node_modules/.bin/eslint ]; "
                           "then node_modules/.bin/eslint .; fi",
                "description": "d",
            }],
        }))
        install_item_hooks(
            item_type="skill", item_key="demo", item_version="1.0.0",
            item_dir=item_dir, repo_root=repo_root, agents=["git"],
        )
        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]
        assert not any(r.repaired for r in repair_repo(repo_root))

    def test_guarded_command_is_a_no_op_when_the_script_is_absent(
        self, tmp_path
    ):
        """The whole point: a clone missing the skill must not fail the edit."""
        import shutil
        import subprocess

        repo_root = TestStaleAbsolutePaths._install_repo_local(tmp_path)
        settings = json.loads(
            (repo_root / ".claude/settings.json").read_text()
        )
        cmd = settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"]

        # Simulate the clone: settings.json is tracked, the skill isn't.
        shutil.rmtree(repo_root / ".claude" / "skills")

        proc = subprocess.run(
            ["sh", "-c", cmd],
            env={"CLAUDE_PROJECT_DIR": str(repo_root), "PATH": os.environ["PATH"]},
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stderr == ""

    def test_guarded_command_still_runs_the_script_when_present(self, tmp_path):
        import subprocess

        repo_root = TestStaleAbsolutePaths._install_repo_local(tmp_path)
        settings = json.loads(
            (repo_root / ".claude/settings.json").read_text()
        )
        cmd = settings["hooks"]["PostToolUse"][0]["hooks"][0]["command"]

        proc = subprocess.run(
            ["sh", "-c", cmd],
            env={"CLAUDE_PROJECT_DIR": str(repo_root), "PATH": os.environ["PATH"]},
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "ok"
