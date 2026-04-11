"""Tests for the three-level similarity scan engine."""

import hashlib
from pathlib import Path

import pytest

from aec.lib.similarity import (
    _jaccard_similarity,
    _size_prefilter,
    normalize_name,
    scan,
    scan_local_items,
)


# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------


class TestNormalizeName:
    """Test filename normalization."""

    def test_strips_md_extension(self):
        assert normalize_name("backend-architect.md") == "backend-architect"

    def test_lowercases(self):
        assert normalize_name("Backend-Architect.MD") == "backend-architect"

    def test_strips_engineering_prefix(self):
        assert normalize_name("engineering-backend-architect.md") == "backend-architect"

    def test_strips_design_prefix(self):
        assert normalize_name("design-systems-guide.md") == "systems-guide"

    def test_strips_security_prefix(self):
        assert normalize_name("security-audit-checklist.md") == "audit-checklist"

    def test_strips_testing_prefix(self):
        assert normalize_name("testing-standards.md") == "standards"

    def test_strips_marketing_prefix(self):
        assert normalize_name("marketing-campaign.md") == "campaign"

    def test_strips_sales_prefix(self):
        assert normalize_name("sales-playbook.md") == "playbook"

    def test_strips_academic_prefix(self):
        assert normalize_name("academic-research.md") == "research"

    def test_strips_paid_media_prefix(self):
        assert normalize_name("paid-media-strategy.md") == "strategy"

    def test_no_prefix_no_extension(self):
        assert normalize_name("code-reviewer") == "code-reviewer"

    def test_preserves_hyphens(self):
        assert normalize_name("my-cool-agent.md") == "my-cool-agent"

    def test_no_underscore_conversion(self):
        assert normalize_name("my_cool_agent.md") == "my_cool_agent"

    def test_only_strips_first_matching_prefix(self):
        # Only the first matching prefix should be stripped
        assert normalize_name("engineering-design-tool.md") == "design-tool"

    def test_empty_string(self):
        assert normalize_name("") == ""

    def test_just_md_extension(self):
        assert normalize_name(".md") == ""

    def test_plain_name_no_match(self):
        assert normalize_name("custom-helper.md") == "custom-helper"


# ---------------------------------------------------------------------------
# scan_local_items
# ---------------------------------------------------------------------------


class TestScanLocalItems:
    """Test local item enumeration."""

    def test_finds_files(self, tmp_path: Path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "code-reviewer.md").write_text("# Code Reviewer")
        (agents_dir / "architect.md").write_text("# Architect")

        items = scan_local_items(agents_dir, "agents", {})
        names = [i["name"] for i in items]
        assert "code-reviewer" in names
        assert "architect" in names
        assert len(items) == 2

    def test_finds_directories(self, tmp_path: Path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        skill = skills_dir / "webapp-testing"
        skill.mkdir()
        (skill / "SKILL.md").write_text("# Skill")

        items = scan_local_items(skills_dir, "skills", {})
        assert len(items) == 1
        assert items[0]["name"] == "webapp-testing"
        assert items[0]["is_dir"] is True

    def test_excludes_installed(self, tmp_path: Path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "code-reviewer.md").write_text("# CR")
        (agents_dir / "architect.md").write_text("# Arch")

        installed = {"code-reviewer": {"version": "1.0.0"}}
        items = scan_local_items(agents_dir, "agents", installed)
        assert len(items) == 1
        assert items[0]["name"] == "architect"

    def test_excludes_hidden_files(self, tmp_path: Path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / ".hidden.md").write_text("secret")
        (agents_dir / "visible.md").write_text("public")

        items = scan_local_items(agents_dir, "agents", {})
        assert len(items) == 1
        assert items[0]["name"] == "visible"

    def test_empty_directory(self, tmp_path: Path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        items = scan_local_items(empty_dir, "agents", {})
        assert items == []

    def test_nonexistent_directory(self, tmp_path: Path):
        items = scan_local_items(tmp_path / "nope", "agents", {})
        assert items == []

    def test_returns_absolute_paths(self, tmp_path: Path):
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "test.md").write_text("# Test")

        items = scan_local_items(agents_dir, "agents", {})
        path = Path(items[0]["path"])
        assert path.is_absolute()


# ---------------------------------------------------------------------------
# _jaccard_similarity
# ---------------------------------------------------------------------------


class TestJaccardSimilarity:
    """Test Jaccard line-set similarity computation."""

    def test_identical_texts(self):
        text = "line one\nline two\nline three\n"
        assert _jaccard_similarity(text, text) == 1.0

    def test_completely_different(self):
        assert _jaccard_similarity("alpha\nbeta\n", "gamma\ndelta\n") == 0.0

    def test_partial_overlap(self):
        a = "shared line\nunique a\n"
        b = "shared line\nunique b\n"
        # intersection = {"shared line"}, union = {"shared line", "unique a", "unique b"}
        assert _jaccard_similarity(a, b) == pytest.approx(1.0 / 3.0)

    def test_whitespace_normalization(self):
        a = "  line   one  \n  line   two  \n"
        b = "line one\nline two\n"
        assert _jaccard_similarity(a, b) == 1.0

    def test_empty_texts(self):
        assert _jaccard_similarity("", "") == 0.0

    def test_one_empty(self):
        assert _jaccard_similarity("something\n", "") == 0.0

    def test_blank_lines_ignored(self):
        a = "line one\n\n\nline two\n"
        b = "line one\nline two\n"
        assert _jaccard_similarity(a, b) == 1.0

    def test_high_similarity(self):
        # 9 shared lines + 1 unique = 9/10 = 0.9
        shared = "\n".join(f"line {i}" for i in range(9))
        a = shared + "\nunique a"
        b = shared + "\nunique b"
        assert _jaccard_similarity(a, b) == pytest.approx(9.0 / 11.0)


# ---------------------------------------------------------------------------
# _size_prefilter
# ---------------------------------------------------------------------------


class TestSizePrefilter:
    """Test size pre-filter for deep scan."""

    def test_same_size(self):
        assert _size_prefilter(100, 100) is True

    def test_within_5x(self):
        assert _size_prefilter(100, 400) is True

    def test_exactly_5x(self):
        assert _size_prefilter(100, 500) is True

    def test_exceeds_5x(self):
        assert _size_prefilter(100, 501) is False

    def test_zero_size_a(self):
        assert _size_prefilter(0, 100) is False

    def test_zero_size_b(self):
        assert _size_prefilter(100, 0) is False

    def test_both_zero(self):
        assert _size_prefilter(0, 0) is False

    def test_reverse_order(self):
        assert _size_prefilter(500, 100) is True
        assert _size_prefilter(501, 100) is False


# ---------------------------------------------------------------------------
# Helpers for building test fixtures
# ---------------------------------------------------------------------------


def _hash_content(content: str) -> str:
    """Compute sha256 hash matching the engine's file hash format."""
    h = hashlib.sha256()
    h.update(content.encode("utf-8"))
    return f"sha256:{h.hexdigest()}"


def _make_file(parent: Path, name: str, content: str) -> dict:
    """Create a file and return a local_items entry."""
    filepath = parent / name
    filepath.write_text(content, encoding="utf-8")
    return {
        "name": filepath.stem,
        "path": str(filepath.resolve()),
        "is_dir": False,
    }


# ---------------------------------------------------------------------------
# Quick scan (depth=1)
# ---------------------------------------------------------------------------


class TestQuickScan:
    """Test depth-1 name-only matching."""

    def test_exact_name_match(self, tmp_path: Path):
        item = _make_file(tmp_path, "code-reviewer.md", "# Local CR")
        catalog = {"code-reviewer": {"version": "1.0.0"}}

        results = scan([item], catalog, depth=1)
        assert len(results) == 1
        assert results[0].catalog_item == "code-reviewer"
        assert results[0].match_type == "exact"
        assert results[0].scan_depth == 1

    def test_normalized_name_match(self, tmp_path: Path):
        item = _make_file(tmp_path, "engineering-code-reviewer.md", "# Local")
        catalog = {"code-reviewer": {"version": "1.0.0"}}

        results = scan([item], catalog, depth=1)
        assert len(results) == 1
        assert results[0].catalog_item == "code-reviewer"

    def test_catalog_with_prefix_matches_plain_local(self, tmp_path: Path):
        item = _make_file(tmp_path, "code-reviewer.md", "# Local")
        catalog = {"engineering-code-reviewer": {"version": "1.0.0"}}

        results = scan([item], catalog, depth=1)
        assert len(results) == 1
        assert results[0].catalog_item == "engineering-code-reviewer"

    def test_no_match(self, tmp_path: Path):
        item = _make_file(tmp_path, "custom-agent.md", "# Custom")
        catalog = {"code-reviewer": {"version": "1.0.0"}}

        results = scan([item], catalog, depth=1)
        assert len(results) == 0

    def test_empty_catalog(self, tmp_path: Path):
        item = _make_file(tmp_path, "code-reviewer.md", "# CR")
        results = scan([item], {}, depth=1)
        assert len(results) == 0

    def test_empty_local_items(self):
        catalog = {"code-reviewer": {"version": "1.0.0"}}
        results = scan([], catalog, depth=1)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Normal scan (depth=2)
# ---------------------------------------------------------------------------


class TestNormalScan:
    """Test depth-2 hash comparison."""

    def test_exact_match_same_name_same_hash(self, tmp_path: Path):
        content = "# Code Reviewer\nDo code reviews."
        item = _make_file(tmp_path, "code-reviewer.md", content)
        chash = _hash_content(content)

        catalog = {"code-reviewer": {"version": "1.0.0"}}
        catalog_hashes = {"code-reviewer": chash}

        results = scan([item], catalog, catalog_hashes, depth=2)
        assert len(results) == 1
        assert results[0].match_type == "exact"
        assert results[0].similarity == 1.0
        assert results[0].local_hash == chash
        assert results[0].scan_depth == 2

    def test_modified_same_name_different_hash(self, tmp_path: Path):
        item = _make_file(tmp_path, "code-reviewer.md", "# Modified version")
        catalog = {"code-reviewer": {"version": "1.0.0"}}
        catalog_hashes = {"code-reviewer": "sha256:different"}

        results = scan([item], catalog, catalog_hashes, depth=2)
        assert len(results) == 1
        assert results[0].match_type == "modified"
        assert results[0].similarity == 1.0

    def test_renamed_different_name_same_hash(self, tmp_path: Path):
        content = "# The original content"
        item = _make_file(tmp_path, "my-custom-name.md", content)
        chash = _hash_content(content)

        catalog = {"code-reviewer": {"version": "2.0.0"}}
        catalog_hashes = {"code-reviewer": chash}

        results = scan([item], catalog, catalog_hashes, depth=2)
        assert len(results) == 1
        assert results[0].match_type == "renamed"
        assert results[0].catalog_item == "code-reviewer"
        assert results[0].similarity == 1.0

    def test_no_catalog_hash_falls_back_to_modified(self, tmp_path: Path):
        item = _make_file(tmp_path, "code-reviewer.md", "# Local")
        catalog = {"code-reviewer": {"version": "1.0.0"}}

        results = scan([item], catalog, catalog_hashes={}, depth=2)
        assert len(results) == 1
        assert results[0].match_type == "modified"

    def test_multiple_items_mixed_results(self, tmp_path: Path):
        content_exact = "# Exact content"
        exact_hash = _hash_content(content_exact)

        item_exact = _make_file(tmp_path, "architect.md", content_exact)
        item_modified = _make_file(tmp_path, "reviewer.md", "# Different")
        item_unmatched = _make_file(tmp_path, "custom.md", "# Custom")

        catalog = {
            "architect": {"version": "1.0.0"},
            "reviewer": {"version": "1.0.0"},
        }
        catalog_hashes = {
            "architect": exact_hash,
            "reviewer": "sha256:original",
        }

        results = scan(
            [item_exact, item_modified, item_unmatched],
            catalog,
            catalog_hashes,
            depth=2,
        )
        by_name = {r.local_name: r for r in results}
        assert by_name["architect"].match_type == "exact"
        assert by_name["reviewer"].match_type == "modified"
        assert "custom" not in by_name


# ---------------------------------------------------------------------------
# Deep scan (depth=3)
# ---------------------------------------------------------------------------


class TestDeepScan:
    """Test depth-3 content similarity."""

    def test_similar_content_above_threshold(self, tmp_path: Path):
        # Create two files with high overlap (12 shared, 2 unique each -> 12/16 = 0.75)
        shared = "\n".join(f"shared line {i}" for i in range(12))
        local_content = shared + "\nlocal unique line 1\nlocal unique line 2"
        catalog_content = shared + "\ncatalog unique line 1\ncatalog unique line 2"

        item = _make_file(tmp_path, "my-agent.md", local_content)

        # Create catalog source file
        catalog_src = tmp_path / "catalog"
        catalog_src.mkdir()
        (catalog_src / "pro-agent.md").write_text(catalog_content, encoding="utf-8")

        catalog = {
            "pro-agent": {
                "version": "1.0.0",
                "source_path": str(catalog_src / "pro-agent.md"),
            }
        }

        results = scan([item], catalog, catalog_hashes={}, depth=3)
        assert len(results) == 1
        assert results[0].match_type == "similar"
        assert results[0].similarity >= 0.70
        assert results[0].catalog_item == "pro-agent"
        assert results[0].scan_depth == 3

    def test_below_threshold_no_match(self, tmp_path: Path):
        local_content = "completely\ndifferent\ncontent\nhere"
        catalog_content = "nothing\nin\ncommon\nat all\nwith local\nstuff"

        item = _make_file(tmp_path, "my-agent.md", local_content)

        catalog_src = tmp_path / "catalog"
        catalog_src.mkdir()
        (catalog_src / "other.md").write_text(catalog_content, encoding="utf-8")

        catalog = {
            "other": {
                "version": "1.0.0",
                "source_path": str(catalog_src / "other.md"),
            }
        }

        results = scan([item], catalog, catalog_hashes={}, depth=3)
        assert len(results) == 0

    def test_size_prefilter_skips_large_difference(self, tmp_path: Path):
        small_content = "tiny"
        large_content = "\n".join(f"line {i}" for i in range(1000))

        item = _make_file(tmp_path, "small.md", small_content)

        catalog_src = tmp_path / "catalog"
        catalog_src.mkdir()
        (catalog_src / "big.md").write_text(large_content, encoding="utf-8")

        catalog = {
            "big": {
                "version": "1.0.0",
                "source_path": str(catalog_src / "big.md"),
            }
        }

        results = scan([item], catalog, catalog_hashes={}, depth=3)
        assert len(results) == 0

    def test_deep_only_checks_unmatched_items(self, tmp_path: Path):
        # name-matched item should NOT be re-checked in deep scan
        content = "# Code Reviewer\nReview code."
        item_matched = _make_file(tmp_path, "code-reviewer.md", content)
        item_unmatched = _make_file(tmp_path, "custom.md", "unrelated\nstuff")

        catalog = {"code-reviewer": {"version": "1.0.0"}}
        catalog_hashes = {"code-reviewer": "sha256:different"}

        results = scan(
            [item_matched, item_unmatched], catalog, catalog_hashes, depth=3
        )
        # code-reviewer should be "modified" from depth 2, custom should have no match
        assert len(results) == 1
        assert results[0].local_name == "code-reviewer"
        assert results[0].match_type == "modified"

    def test_best_match_selected(self, tmp_path: Path):
        # Local file should match the catalog item with highest similarity
        shared = "\n".join(f"shared line {i}" for i in range(12))
        local_content = shared + "\nlocal extra 1\nlocal extra 2"
        good_match = shared + "\ncatalog extra 1\ncatalog extra 2"
        bad_match = "totally\ndifferent\ncontent\nhere\nnothing shared"

        item = _make_file(tmp_path, "my-thing.md", local_content)

        catalog_src = tmp_path / "catalog"
        catalog_src.mkdir()
        (catalog_src / "good.md").write_text(good_match, encoding="utf-8")
        (catalog_src / "bad.md").write_text(bad_match, encoding="utf-8")

        catalog = {
            "good": {"version": "1.0.0", "source_path": str(catalog_src / "good.md")},
            "bad": {"version": "1.0.0", "source_path": str(catalog_src / "bad.md")},
        }

        results = scan([item], catalog, catalog_hashes={}, depth=3)
        assert len(results) == 1
        assert results[0].catalog_item == "good"


# ---------------------------------------------------------------------------
# Edge cases and validation
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases and input validation."""

    def test_invalid_depth_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="depth must be 1, 2, or 3"):
            scan([], {}, depth=0)

    def test_invalid_depth_4_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="depth must be 1, 2, or 3"):
            scan([], {}, depth=4)

    def test_empty_catalog_empty_locals(self):
        results = scan([], {}, depth=1)
        assert results == []

    def test_results_sorted_by_local_name(self, tmp_path: Path):
        items = [
            _make_file(tmp_path, "zebra.md", "z"),
            _make_file(tmp_path, "alpha.md", "a"),
            _make_file(tmp_path, "middle.md", "m"),
        ]
        catalog = {
            "zebra": {"version": "1.0.0"},
            "alpha": {"version": "1.0.0"},
            "middle": {"version": "1.0.0"},
        }
        results = scan(items, catalog, depth=1)
        names = [r.local_name for r in results]
        assert names == ["alpha", "middle", "zebra"]

    def test_catalog_hashes_defaults_to_empty(self, tmp_path: Path):
        item = _make_file(tmp_path, "code-reviewer.md", "# CR")
        catalog = {"code-reviewer": {"version": "1.0.0"}}

        # depth=2 with no catalog_hashes should not crash
        results = scan([item], catalog, depth=2)
        assert len(results) == 1
        assert results[0].match_type == "modified"
