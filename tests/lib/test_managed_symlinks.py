"""Tests for aec.lib.managed_symlinks -- the symlink ownership record.

conftest.py's autouse _isolate_managed_symlinks fixture points
MANAGED_SYMLINKS_PATH at a per-test tmp_path, so these never touch the
developer's real ~/.agents-environment-config/managed-symlinks.json.
"""

import json
from pathlib import Path

import pytest

from aec.lib import managed_symlinks as ms
from aec.lib.filesystem import create_symlink, is_our_symlink, remove_symlink


class TestRecordSymlink:
    def test_record_then_is_recorded(self, temp_dir):
        link = temp_dir / "link"
        source = temp_dir / "source"

        ms.record_symlink(link, source)

        assert ms.is_recorded(link) is True

    def test_unrecorded_path_is_not_recorded(self, temp_dir):
        assert ms.is_recorded(temp_dir / "never-touched") is False

    def test_record_stores_source(self, temp_dir):
        link = temp_dir / "link"
        source = temp_dir / "source"

        ms.record_symlink(link, source)

        data = json.loads(ms.MANAGED_SYMLINKS_PATH.read_text())
        entry = data["links"][str(link.expanduser().absolute())]
        assert entry["source"] == str(source.expanduser().absolute())

    def test_key_is_not_resolved(self, temp_dir):
        """A dangling link (or one under a moved dir) must still be keyed by
        its own path, not by following it -- that's the whole point of the
        record over the old resolve()-based heuristic."""
        link = temp_dir / "dangling-link"
        source = temp_dir / "does-not-exist" / "source"

        ms.record_symlink(link, source)

        assert ms.is_recorded(link) is True


class TestForgetSymlink:
    def test_forget_removes_entry(self, temp_dir):
        link = temp_dir / "link"
        ms.record_symlink(link, temp_dir / "source")

        ms.forget_symlink(link)

        assert ms.is_recorded(link) is False

    def test_forget_unrecorded_path_is_a_noop(self, temp_dir):
        # Must not raise or create a file for a path never recorded.
        ms.forget_symlink(temp_dir / "never-recorded")
        assert not ms.MANAGED_SYMLINKS_PATH.exists()


class TestCreateSymlinkRecordsOwnership:
    def test_create_symlink_records_the_link(self, temp_dir):
        source = temp_dir / "source.txt"
        source.write_text("content")
        target = temp_dir / "link.txt"

        assert create_symlink(source, target) is True

        assert ms.is_recorded(target) is True
        assert is_our_symlink(target) is True

    def test_remove_symlink_forgets_the_link(self, temp_dir):
        source = temp_dir / "source.txt"
        source.write_text("content")
        target = temp_dir / "link.txt"
        create_symlink(source, target)

        assert remove_symlink(target) is True

        assert ms.is_recorded(target) is False


class TestMovedCheckoutUnderNonStandardName:
    """The bug this plan fixes: a checkout cloned under a directory NOT
    named agents-environment-config produces links the old substring
    heuristic never recognised as AEC's, so a subsequent move/reclone left
    them dangling and unrepaired forever. The record fixes this because
    ownership is keyed by the link's own path, not by what it points to.
    """

    def test_link_from_non_standard_checkout_survives_a_move(self, temp_dir):
        checkout = temp_dir / "my-checkout"  # deliberately NOT "agents-environment-config"
        (checkout / "sub").mkdir(parents=True)
        source = checkout / "sub" / "file.txt"
        source.write_text("content")
        target = temp_dir / "link.txt"

        create_symlink(source, target)
        assert is_our_symlink(target) is True

        # Simulate moving/recloning the checkout to a new location/name.
        moved = temp_dir / "my-checkout-renamed"
        checkout.rename(moved)

        # The link is now dangling, but ownership is still recognised --
        # it never depended on the (now-broken) target path.
        assert is_our_symlink(target) is True


class TestUnrelatedLinkNotAdopted:
    def test_foreign_link_matching_old_substrings_is_not_ours(self, temp_dir, monkeypatch):
        """Seed the record (simulating a completed migration / other AEC
        links already known) and confirm an unrelated link whose target
        happens to contain 'agents-environment-config' is never adopted.
        The old heuristic would have falsely claimed this link; the record
        makes it explicit that only recorded links are ours.
        """
        # Prevent the legacy migration scan from finding real candidate
        # locations on this machine (it also derives CLAUDE_DIR etc. from
        # the isolated test HOME, but keep this test self-contained).
        monkeypatch.setattr(ms, "_legacy_candidate_paths", lambda: [])

        # Seed the record with an unrelated entry so the file exists,
        # matching "once the record exists" -- no candidate scan runs again.
        ms.record_symlink(temp_dir / "some-other-link", temp_dir / "some-other-source")

        foreign_target_dir = temp_dir / "unrelated-project" / "agents-environment-config-notes"
        foreign_target_dir.mkdir(parents=True)
        foreign_link = temp_dir / "foreign-link"
        foreign_link.symlink_to(foreign_target_dir)

        assert is_our_symlink(foreign_link) is False


class TestLegacyMigration:
    def test_migration_adopts_matching_legacy_link(self, temp_dir, monkeypatch):
        legacy_link = temp_dir / "legacy-link"
        legacy_link.symlink_to(temp_dir / "somewhere" / "agents-environment-config" / "thing")
        monkeypatch.setattr(ms, "_legacy_candidate_paths", lambda: [legacy_link])

        assert is_our_symlink(legacy_link) is True
        assert ms.is_recorded(legacy_link) is True

    def test_ownership_lookup_never_writes(self, temp_dir, monkeypatch):
        """Reads must not create the record: dry runs promise no changes."""
        legacy_link = temp_dir / "legacy-link"
        legacy_link.symlink_to(temp_dir / "somewhere" / "agents-environment-config" / "thing")
        monkeypatch.setattr(ms, "_legacy_candidate_paths", lambda: [legacy_link])

        assert is_our_symlink(legacy_link) is True
        assert not ms.MANAGED_SYMLINKS_PATH.exists()

    def test_first_record_write_persists_adopted_links(self, temp_dir, monkeypatch):
        """Once the file exists the heuristic is never consulted again, so
        the first write must carry the adopted legacy links with it."""
        legacy_link = temp_dir / "legacy-link"
        legacy_link.symlink_to(temp_dir / "somewhere" / "agents-environment-config" / "thing")
        monkeypatch.setattr(ms, "_legacy_candidate_paths", lambda: [legacy_link])

        ms.record_symlink(temp_dir / "new-link", temp_dir / "source")

        monkeypatch.setattr(ms, "_legacy_candidate_paths", lambda: [])
        assert is_our_symlink(legacy_link) is True

    def test_unwritable_store_does_not_break_ownership_check(self, temp_dir, monkeypatch):
        def fail(_data):
            raise OSError("read-only state dir")

        monkeypatch.setattr(ms, "_save", fail)
        legacy_link = temp_dir / "legacy-link"
        legacy_link.symlink_to(temp_dir / "somewhere" / "agents-environment-config" / "thing")
        monkeypatch.setattr(ms, "_legacy_candidate_paths", lambda: [legacy_link])

        assert is_our_symlink(legacy_link) is True


class TestReviewRegressions:
    """Regressions from the PR #93 review."""

    def test_migration_runs_before_first_new_record(self, temp_dir, monkeypatch):
        """A new link recorded before any ownership check (install's setup
        step runs first) must not skip adopting pre-existing legacy links."""
        legacy_link = temp_dir / "legacy-statusline.sh"
        legacy_link.symlink_to(temp_dir / "old" / "agents-environment-config" / "statusline.sh")
        monkeypatch.setattr(ms, "_legacy_candidate_paths", lambda: [legacy_link])

        source = temp_dir / "source.txt"
        source.write_text("x")
        assert create_symlink(source, temp_dir / "new-link")

        assert is_our_symlink(legacy_link) is True

    def test_user_replacement_at_recorded_path_is_not_ours(self, temp_dir):
        source = temp_dir / "source.txt"
        source.write_text("x")
        link = temp_dir / "link"
        assert create_symlink(source, link)

        link.unlink()
        users_own = temp_dir / "users-own.txt"
        users_own.write_text("mine")
        link.symlink_to(users_own)

        assert is_our_symlink(link) is False

    def test_record_failure_rolls_back_link(self, temp_dir, monkeypatch):
        def fail(*_args):
            raise OSError("read-only state dir")

        monkeypatch.setattr(ms, "record_symlink", fail)
        source = temp_dir / "source.txt"
        source.write_text("x")
        link = temp_dir / "link"

        assert create_symlink(source, link) is False
        assert not link.is_symlink() and not link.exists()

    def test_setup_repoints_managed_links_after_checkout_move(self, temp_dir, monkeypatch):
        from aec.commands import agent_tools

        agent_tools_dir = temp_dir / ".agent-tools"
        checkout = temp_dir / "my-checkout"  # not named agents-environment-config
        for sub in (".agent-rules", ".claude/agents", ".cursor/commands"):
            (checkout / sub).mkdir(parents=True)

        monkeypatch.setattr(agent_tools, "AGENT_TOOLS_DIR", agent_tools_dir)
        monkeypatch.setattr(agent_tools, "_is_claude_installed", lambda: False)
        monkeypatch.setattr(agent_tools, "_is_cursor_installed", lambda: False)
        monkeypatch.setattr(agent_tools, "get_repo_root", lambda: checkout)
        agent_tools.setup()

        moved = temp_dir / "moved-checkout"
        checkout.rename(moved)
        monkeypatch.setattr(agent_tools, "get_repo_root", lambda: moved)
        agent_tools.setup()

        rules = agent_tools_dir / "rules" / "agents-environment-config"
        assert rules.resolve() == (moved / ".agent-rules").resolve()

    def test_setup_dry_run_does_not_create_record(self, temp_dir, monkeypatch):
        from aec.commands import agent_tools

        agent_tools_dir = temp_dir / ".agent-tools"
        checkout = temp_dir / "agents-environment-config"
        (checkout / ".agent-rules").mkdir(parents=True)
        rules = agent_tools_dir / "rules" / "agents-environment-config"
        rules.parent.mkdir(parents=True)
        rules.symlink_to(temp_dir / "old" / "agents-environment-config" / ".agent-rules")

        monkeypatch.setattr(agent_tools, "AGENT_TOOLS_DIR", agent_tools_dir)
        monkeypatch.setattr(agent_tools, "_is_claude_installed", lambda: False)
        monkeypatch.setattr(agent_tools, "_is_cursor_installed", lambda: False)
        monkeypatch.setattr(agent_tools, "get_repo_root", lambda: checkout)
        monkeypatch.setattr(ms, "_legacy_candidate_paths", lambda: [rules])
        agent_tools.setup(dry_run=True)

        assert not ms.MANAGED_SYMLINKS_PATH.exists()

    def test_setup_persists_migration_when_nothing_to_create(self, temp_dir, monkeypatch):
        """An upgrade with every link already present must still retire the
        heuristic, or a later user symlink matching it would be adopted."""
        from aec.commands import agent_tools

        agent_tools_dir = temp_dir / ".agent-tools"
        checkout = temp_dir / "agents-environment-config"
        (checkout / ".agent-rules").mkdir(parents=True)
        rules = agent_tools_dir / "rules" / "agents-environment-config"
        rules.parent.mkdir(parents=True)
        rules.symlink_to(checkout / ".agent-rules")
        user_link = temp_dir / "user-link"
        user_link.symlink_to(temp_dir / "elsewhere" / "agents-environment-config")

        candidates = [rules]
        monkeypatch.setattr(ms, "_legacy_candidate_paths", lambda: candidates)
        monkeypatch.setattr(agent_tools, "AGENT_TOOLS_DIR", agent_tools_dir)
        monkeypatch.setattr(agent_tools, "_is_claude_installed", lambda: False)
        monkeypatch.setattr(agent_tools, "_is_cursor_installed", lambda: False)
        monkeypatch.setattr(agent_tools, "get_repo_root", lambda: checkout)
        agent_tools.setup()

        assert ms.MANAGED_SYMLINKS_PATH.exists()
        assert is_our_symlink(rules) is True
        candidates.append(user_link)  # heuristic would claim this if still live
        assert is_our_symlink(user_link) is False

    def test_concurrent_records_keep_every_entry(self, temp_dir):
        import multiprocessing as mp

        links = [temp_dir / f"link-{i}" for i in range(16)]
        ctx = mp.get_context("fork")
        procs = [ctx.Process(target=ms.record_symlink, args=(l, temp_dir / "src")) for l in links]
        for p in procs:
            p.start()
        for p in procs:
            p.join()

        assert all(ms.is_recorded(l) for l in links)
