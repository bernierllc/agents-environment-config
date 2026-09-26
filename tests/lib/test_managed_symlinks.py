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
    def test_migration_adopts_matching_legacy_link_once(self, temp_dir, monkeypatch):
        legacy_link = temp_dir / "legacy-link"
        legacy_link.symlink_to(temp_dir / "somewhere" / "agents-environment-config" / "thing")
        monkeypatch.setattr(ms, "_legacy_candidate_paths", lambda: [legacy_link])

        assert not ms.MANAGED_SYMLINKS_PATH.exists()

        assert is_our_symlink(legacy_link) is True
        assert ms.MANAGED_SYMLINKS_PATH.exists()
        assert ms.is_recorded(legacy_link) is True

    def test_migration_writes_record_even_with_no_matches(self, temp_dir, monkeypatch):
        """The record file must exist after the first check even when
        nothing matched, so the heuristic is never consulted again."""
        monkeypatch.setattr(ms, "_legacy_candidate_paths", lambda: [])
        source = temp_dir / "source.txt"
        source.write_text("x")
        unrelated_link = temp_dir / "unrelated-link"
        unrelated_link.symlink_to(source)  # a symlink, but not AEC's

        assert is_our_symlink(unrelated_link) is False
        assert ms.MANAGED_SYMLINKS_PATH.exists()

    def test_migration_runs_only_once(self, temp_dir, monkeypatch):
        legacy_link = temp_dir / "legacy-link"
        legacy_link.symlink_to(temp_dir / "somewhere" / "agents-environment-config" / "thing")

        calls = {"n": 0}

        def counting_candidates():
            calls["n"] += 1
            return [legacy_link]

        monkeypatch.setattr(ms, "_legacy_candidate_paths", counting_candidates)

        is_our_symlink(legacy_link)
        is_our_symlink(legacy_link)
        is_our_symlink(legacy_link)

        assert calls["n"] == 1
