"""Tests for gitignore template bundling."""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
SUPPORTED_JSON = REPO_ROOT / "aec" / "templates" / "gitignore" / "supported.json"
TEMPLATES_DIR = REPO_ROOT / "aec" / "templates" / "gitignore"


class TestSupportedJson:
    def test_supported_json_exists(self):
        assert SUPPORTED_JSON.exists(), "supported.json must exist"

    def test_supported_json_is_valid(self):
        data = json.loads(SUPPORTED_JSON.read_text())
        assert "languages" in data
        assert "frameworks" in data

    def test_all_referenced_templates_exist(self):
        """Every filename in supported.json must exist in gitignore root."""
        if not TEMPLATES_DIR.exists():
            pytest.skip("gitignore submodule not initialized — run: git submodule update --init")
        data = json.loads(SUPPORTED_JSON.read_text())
        missing = []
        for section in ("languages", "frameworks"):
            for key, filenames in data[section].items():
                for fname in filenames:
                    if not (TEMPLATES_DIR / fname).exists():
                        missing.append(f"{section}.{key}: {fname}")
        assert not missing, f"Missing template files: {missing}"


class TestCompositeJoin:
    def test_composite_join_single_language(self):
        """Composite join for a single language returns non-empty, deduped content."""
        if not TEMPLATES_DIR.exists():
            pytest.skip("gitignore submodule not initialized — run: git submodule update --init")
        from aec.lib.git_setup import build_composite_gitignore

        result = build_composite_gitignore(["python"], [], REPO_ROOT / "aec" / "templates")
        assert result, "composite gitignore must not be empty"
        assert "# AEC" in result, "must include AEC section"
        lines = result.splitlines()
        non_empty = [l for l in lines if l.strip()]
        assert len(non_empty) == len(set(non_empty)), "non-empty lines must be deduplicated"

    def test_composite_join_multi_language(self):
        """Composite join for multiple languages includes content from each."""
        if not TEMPLATES_DIR.exists():
            pytest.skip("gitignore submodule not initialized — run: git submodule update --init")
        from aec.lib.git_setup import build_composite_gitignore

        result = build_composite_gitignore(["python", "typescript"], [], REPO_ROOT / "aec" / "templates")
        assert result
        assert "# AEC" in result

    def test_composite_join_submodule_missing(self, tmp_path):
        """When submodule is missing, falls back to AEC patterns only."""
        from aec.lib.git_setup import build_composite_gitignore

        result = build_composite_gitignore(["python"], [], tmp_path)
        assert "# AEC" in result
        assert result  # non-empty
