"""Tests for finding/replacing the blurb block inside agent files."""

import pytest

from aec.lib.agent_blurb.markers import (
    find_block,
    replace_block,
    BlockNotFoundError,
    MalformedBlockError,
)


CLEAN_FILE_NO_BLOCK = """# CLAUDE.md

Some user content.

More content here.
"""

CLEAN_FILE_WITH_BLOCK = """# CLAUDE.md

Some user content.

<!-- aec-blurb:start v1 schema=1 aec=2.37.4 template-hash=abc content-hash=def profile=balanced scope=project -->
Body content
across lines
<!-- aec-blurb:end -->

After the block.
"""

DUPLICATE_START = """# CLAUDE.md
<!-- aec-blurb:start v1 ... -->
body
<!-- aec-blurb:end -->
<!-- aec-blurb:start v1 ... -->
body2
<!-- aec-blurb:end -->
"""

MISSING_END = """# CLAUDE.md
<!-- aec-blurb:start v1 ... -->
body, never ends
"""


class TestFindBlock:
    def test_no_block_returns_none(self):
        assert find_block(CLEAN_FILE_NO_BLOCK) is None

    def test_finds_existing_block(self):
        loc = find_block(CLEAN_FILE_WITH_BLOCK)
        assert loc is not None
        block = CLEAN_FILE_WITH_BLOCK[loc.start:loc.end]
        assert block.startswith("<!-- aec-blurb:start")
        assert block.rstrip().endswith("<!-- aec-blurb:end -->")

    def test_duplicate_start_raises(self):
        with pytest.raises(MalformedBlockError, match="duplicate"):
            find_block(DUPLICATE_START)

    def test_missing_end_raises(self):
        with pytest.raises(MalformedBlockError, match="missing end"):
            find_block(MISSING_END)


class TestReplaceBlock:
    def test_replace_existing(self):
        new_block = "<!-- aec-blurb:start v1 NEW -->\nnew body\n<!-- aec-blurb:end -->\n"
        result = replace_block(CLEAN_FILE_WITH_BLOCK, new_block)
        assert "Body content" not in result
        assert "new body" in result
        assert "Some user content." in result
        assert "After the block." in result

    def test_append_when_missing(self):
        new_block = "<!-- aec-blurb:start v1 NEW -->\nnew body\n<!-- aec-blurb:end -->\n"
        result = replace_block(CLEAN_FILE_NO_BLOCK, new_block)
        assert "new body" in result
        assert "Some user content." in result
        assert result.endswith(new_block)

    def test_replace_does_not_corrupt_surrounding(self):
        new_block = "<!-- aec-blurb:start v1 X -->\nx\n<!-- aec-blurb:end -->\n"
        result = replace_block(CLEAN_FILE_WITH_BLOCK, new_block)
        lines = result.splitlines()
        assert "# CLAUDE.md" in lines
        assert "After the block." in lines


class TestBlockNotFoundError:
    def test_is_exception_subclass(self):
        assert issubclass(BlockNotFoundError, Exception)
