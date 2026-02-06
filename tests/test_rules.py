"""Tests for aec.commands.rules module."""

from pathlib import Path

import pytest

from aec.commands.rules import _strip_frontmatter


class TestStripFrontmatter:
    """Test frontmatter stripping."""

    def test_strips_yaml_frontmatter(self):
        """Should strip YAML frontmatter from content."""
        content = """---
description: Test rule
globs: ["*.py"]
---
# Rule Title

This is the rule content.
"""
        result = _strip_frontmatter(content)

        assert "---" not in result
        assert "description:" not in result
        assert "# Rule Title" in result
        assert "This is the rule content." in result

    def test_handles_no_frontmatter(self):
        """Should return content unchanged if no frontmatter."""
        content = """# Rule Title

This is the rule content.
"""
        result = _strip_frontmatter(content)

        assert result == content

    def test_handles_unclosed_frontmatter(self):
        """Should return original if frontmatter is not closed."""
        content = """---
description: Test rule

# Rule Title

This is missing the closing ---.
"""
        result = _strip_frontmatter(content)

        # Should return original since frontmatter is not properly closed
        assert result == content

    def test_handles_empty_content(self):
        """Should handle empty content."""
        result = _strip_frontmatter("")
        assert result == ""

    def test_handles_only_frontmatter(self):
        """Should handle content that is only frontmatter."""
        content = """---
description: Test
---
"""
        result = _strip_frontmatter(content)

        # Should return empty or whitespace
        assert result.strip() == ""

    def test_preserves_content_after_frontmatter(self):
        """Should preserve all content after frontmatter."""
        content = """---
key: value
---
Line 1
Line 2

Line 4 (after blank)
"""
        result = _strip_frontmatter(content)

        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 4" in result
        assert "key: value" not in result
