"""Tests for aec.lib.hooks.git_blocks — idempotent delimited-block writer."""

import sys

import pytest


class TestGitBlocks:
    def test_write_to_empty_file_creates_shebang_and_block(self, tmp_path):
        from aec.lib.hooks.git_blocks import write_block
        hook_file = tmp_path / "pre-commit"
        write_block(hook_file, item_key="skill:foo", hook_id="lint", version="1.0.0",
                    command="echo lint")
        text = hook_file.read_text()
        assert text.startswith("#!/usr/bin/env bash") or text.startswith("#!/bin/sh")
        assert "# >>> AEC:BEGIN item=skill:foo hook_id=lint" in text
        assert "# <<< AEC:END" in text
        assert "echo lint" in text

    def test_write_preserves_existing_user_content(self, tmp_path):
        from aec.lib.hooks.git_blocks import write_block
        hook_file = tmp_path / "pre-commit"
        hook_file.write_text("#!/bin/sh\necho 'user content'\n")
        write_block(hook_file, item_key="skill:foo", hook_id="lint", version="1.0.0",
                    command="echo lint")
        text = hook_file.read_text()
        assert "echo 'user content'" in text
        assert "echo lint" in text

    def test_two_items_coexist(self, tmp_path):
        from aec.lib.hooks.git_blocks import write_block
        hook_file = tmp_path / "pre-commit"
        write_block(hook_file, item_key="skill:foo", hook_id="a", version="1", command="echo a")
        write_block(hook_file, item_key="skill:bar", hook_id="b", version="1", command="echo b")
        text = hook_file.read_text()
        assert text.count("AEC:BEGIN") == 2
        assert "echo a" in text and "echo b" in text

    def test_reinstall_same_block_is_byte_identical(self, tmp_path):
        from aec.lib.hooks.git_blocks import write_block
        hook_file = tmp_path / "pre-commit"
        write_block(hook_file, item_key="skill:foo", hook_id="a", version="1", command="echo a")
        first = hook_file.read_text()
        write_block(hook_file, item_key="skill:foo", hook_id="a", version="1", command="echo a")
        assert hook_file.read_text() == first

    def test_upgrade_replaces_block_in_place(self, tmp_path):
        from aec.lib.hooks.git_blocks import write_block
        hook_file = tmp_path / "pre-commit"
        write_block(hook_file, item_key="skill:foo", hook_id="a", version="1", command="echo old")
        write_block(hook_file, item_key="skill:foo", hook_id="a", version="2", command="echo new")
        text = hook_file.read_text()
        assert "echo new" in text
        assert "echo old" not in text
        assert text.count("AEC:BEGIN") == 1
        assert "version=2" in text

    def test_remove_block_preserves_user_content(self, tmp_path):
        from aec.lib.hooks.git_blocks import remove_block, write_block
        hook_file = tmp_path / "pre-commit"
        hook_file.write_text("#!/bin/sh\necho 'user content'\n")
        write_block(hook_file, item_key="skill:foo", hook_id="a", version="1", command="echo a")
        remove_block(hook_file, item_key="skill:foo", hook_id="a")
        text = hook_file.read_text()
        assert "echo 'user content'" in text
        assert "AEC:BEGIN" not in text

    def test_remove_missing_block_is_noop(self, tmp_path):
        from aec.lib.hooks.git_blocks import remove_block
        hook_file = tmp_path / "pre-commit"
        hook_file.write_text("#!/bin/sh\necho 'user'\n")
        original = hook_file.read_text()
        remove_block(hook_file, item_key="skill:foo", hook_id="nope")
        assert hook_file.read_text() == original

    def test_executable_bit_set_on_posix(self, tmp_path):
        import os
        if sys.platform.startswith("win"):
            pytest.skip("POSIX-only permission semantics")
        from aec.lib.hooks.git_blocks import write_block
        hook_file = tmp_path / "pre-commit"
        write_block(hook_file, item_key="skill:foo", hook_id="a", version="1", command="echo a")
        assert os.access(hook_file, os.X_OK)
