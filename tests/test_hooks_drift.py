"""Tests for aec.lib.hooks.drift — fingerprint-based reconciliation between
recorded hook state and the actual agent settings files.

The whole point: the recorded pointer (index) is a cache, the content
fingerprint is identity. When another tool inserts/removes entries the index
shifts but the hook is still present — verify must find it by fingerprint.
"""

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
        assert cmd.startswith('"$CLAUDE_PROJECT_DIR"/')
        assert str(repo_root) not in cmd
        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]

    def test_portable_install_is_not_stale(self, tmp_path):
        from aec.lib.hooks.drift import Drift, verify_repo

        repo_root = self._install_repo_local(tmp_path)
        assert [s.status for s in verify_repo(repo_root)] == [Drift.OK]
