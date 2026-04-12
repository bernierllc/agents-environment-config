"""Tests for aec.lib.catalog_hashes module."""

import hashlib
import json
from pathlib import Path

import pytest

from aec.lib.catalog_hashes import (
    generate_catalog_hashes,
    hash_single_file,
    load_catalog_hashes,
    regenerate_if_missing,
)


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------


@pytest.fixture
def source_dirs(tmp_path: Path) -> dict:
    """Create mock source dirs with agents, skills, and rules."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    # Create an agent .md file with frontmatter
    agent_file = agents_dir / "backend-architect.md"
    agent_file.write_text(
        "---\n"
        "name: backend-architect\n"
        "version: 1.0.0\n"
        "description: Backend architecture agent\n"
        "---\n"
        "# Backend Architect\n"
        "Content here.\n",
        encoding="utf-8",
    )

    # Create a skill directory with SKILL.md
    skill_dir = skills_dir / "code-review"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: code-review\n"
        "version: 2.1.0\n"
        "description: Code review skill\n"
        "author: test\n"
        "---\n"
        "# Code Review\n",
        encoding="utf-8",
    )
    (skill_dir / "prompt.md").write_text("Review the code.\n", encoding="utf-8")

    # Create a rule .md file with frontmatter
    rule_file = rules_dir / "testing-standards.md"
    rule_file.write_text(
        "---\n"
        "name: testing-standards\n"
        "version: 0.5.0\n"
        "description: Testing standards rule\n"
        "---\n"
        "# Testing Standards\n"
        "Always test.\n",
        encoding="utf-8",
    )

    return {
        "agents": agents_dir,
        "skills": skills_dir,
        "rules": rules_dir,
    }


# -------------------------------------------------------------------
# hash_single_file
# -------------------------------------------------------------------


class TestHashSingleFile:
    def test_returns_sha256_prefix(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.md"
        f.write_text("hello world", encoding="utf-8")
        result = hash_single_file(f)
        assert result.startswith("sha256:")

    def test_correct_digest(self, tmp_path: Path) -> None:
        content = b"deterministic content"
        f = tmp_path / "test.md"
        f.write_bytes(content)
        expected = f"sha256:{hashlib.sha256(content).hexdigest()}"
        assert hash_single_file(f) == expected

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.md"
        f1.write_text("aaa", encoding="utf-8")
        f2 = tmp_path / "b.md"
        f2.write_text("bbb", encoding="utf-8")
        assert hash_single_file(f1) != hash_single_file(f2)


# -------------------------------------------------------------------
# generate_catalog_hashes
# -------------------------------------------------------------------


class TestGenerateCatalogHashes:
    def test_returns_proper_structure(self, source_dirs: dict) -> None:
        catalog = generate_catalog_hashes(source_dirs)
        assert "generatedAt" in catalog
        assert "aecVersion" in catalog
        assert "agents" in catalog
        assert "skills" in catalog
        assert "rules" in catalog

    def test_discovers_agent(self, source_dirs: dict) -> None:
        catalog = generate_catalog_hashes(source_dirs)
        assert "backend-architect" in catalog["agents"]
        entry = catalog["agents"]["backend-architect"]
        assert entry["version"] == "1.0.0"
        assert entry["contentHash"].startswith("sha256:")

    def test_discovers_skill(self, source_dirs: dict) -> None:
        catalog = generate_catalog_hashes(source_dirs)
        assert "code-review" in catalog["skills"]
        entry = catalog["skills"]["code-review"]
        assert entry["version"] == "2.1.0"
        assert entry["contentHash"].startswith("sha256:")

    def test_discovers_rule(self, source_dirs: dict) -> None:
        catalog = generate_catalog_hashes(source_dirs)
        assert "testing-standards" in catalog["rules"]
        entry = catalog["rules"]["testing-standards"]
        assert entry["version"] == "0.5.0"
        assert entry["contentHash"].startswith("sha256:")

    def test_empty_source_dirs(self, tmp_path: Path) -> None:
        empty_dirs = {
            "agents": tmp_path / "empty_agents",
            "skills": tmp_path / "empty_skills",
            "rules": tmp_path / "empty_rules",
        }
        for d in empty_dirs.values():
            d.mkdir()
        catalog = generate_catalog_hashes(empty_dirs)
        assert catalog["agents"] == {}
        assert catalog["skills"] == {}
        assert catalog["rules"] == {}

    def test_agent_hash_matches_hash_single_file(self, source_dirs: dict) -> None:
        """Verify agent hash matches direct hash_single_file call."""
        catalog = generate_catalog_hashes(source_dirs)
        agent_path = source_dirs["agents"] / "backend-architect.md"
        expected = hash_single_file(agent_path)
        assert catalog["agents"]["backend-architect"]["contentHash"] == expected


# -------------------------------------------------------------------
# load_catalog_hashes
# -------------------------------------------------------------------


class TestLoadCatalogHashes:
    def test_returns_empty_on_missing_file(self, tmp_path: Path) -> None:
        result = load_catalog_hashes(tmp_path / "nonexistent.json")
        assert result == {"agents": {}, "skills": {}, "rules": {}}

    def test_returns_empty_on_corrupt_json(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json!", encoding="utf-8")
        result = load_catalog_hashes(bad_file)
        assert result == {"agents": {}, "skills": {}, "rules": {}}

    def test_returns_empty_on_wrong_structure(self, tmp_path: Path) -> None:
        wrong_file = tmp_path / "wrong.json"
        wrong_file.write_text('{"foo": "bar"}', encoding="utf-8")
        result = load_catalog_hashes(wrong_file)
        assert result == {"agents": {}, "skills": {}, "rules": {}}

    def test_loads_valid_file(self, tmp_path: Path) -> None:
        data = {
            "generatedAt": "2026-04-10T18:00:00Z",
            "aecVersion": "2.18.2",
            "agents": {"test": {"version": "1.0.0", "contentHash": "sha256:abc"}},
            "skills": {},
            "rules": {},
        }
        f = tmp_path / "catalog.json"
        f.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        result = load_catalog_hashes(f)
        assert result["agents"]["test"]["version"] == "1.0.0"


# -------------------------------------------------------------------
# regenerate_if_missing
# -------------------------------------------------------------------


class TestRegenerateIfMissing:
    def test_creates_file_when_missing(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog_path = tmp_path / "output" / "catalog-hashes.json"
        result = regenerate_if_missing(catalog_path, source_dirs)
        assert catalog_path.exists()
        assert "agents" in result
        assert "backend-architect" in result["agents"]

    def test_loads_existing_valid_file(self, tmp_path: Path) -> None:
        data = {
            "generatedAt": "2026-04-10T18:00:00Z",
            "aecVersion": "2.18.2",
            "agents": {"cached": {"version": "1.0.0", "contentHash": "sha256:xyz"}},
            "skills": {},
            "rules": {},
        }
        catalog_path = tmp_path / "catalog-hashes.json"
        catalog_path.write_text(json.dumps(data) + "\n", encoding="utf-8")
        result = regenerate_if_missing(catalog_path)
        # Should return the existing data, not regenerate
        assert "cached" in result["agents"]

    def test_regenerates_on_corrupt_file(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog_path = tmp_path / "catalog-hashes.json"
        catalog_path.write_text("CORRUPT!", encoding="utf-8")
        result = regenerate_if_missing(catalog_path, source_dirs)
        # Should have regenerated
        assert "backend-architect" in result["agents"]
        # File should now be valid JSON
        loaded = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert "agents" in loaded


# -------------------------------------------------------------------
# Round-trip: generate, save, load, verify
# -------------------------------------------------------------------


class TestRoundTrip:
    def test_generate_save_load_matches(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog = generate_catalog_hashes(source_dirs)
        catalog_path = tmp_path / "catalog-hashes.json"
        catalog_path.write_text(
            json.dumps(catalog, indent=2) + "\n", encoding="utf-8"
        )
        loaded = load_catalog_hashes(catalog_path)
        assert loaded["agents"] == catalog["agents"]
        assert loaded["skills"] == catalog["skills"]
        assert loaded["rules"] == catalog["rules"]
        assert loaded["aecVersion"] == catalog["aecVersion"]
