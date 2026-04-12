"""Tests for scripts/update-catalog-hashes.py incremental update logic."""

import importlib
import json
import shutil
import sys
from pathlib import Path

import pytest

from aec.lib.catalog_hashes import hash_single_file
from aec.lib.skills_manifest import hash_skill_directory

# Load the script as a module
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "update-catalog-hashes.py"
_spec = importlib.util.spec_from_file_location("update_catalog_hashes", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["update_catalog_hashes"] = _mod
_spec.loader.exec_module(_mod)
incremental_update = _mod.incremental_update


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

    _create_agent(agents_dir, "backend-architect", "1.0.0")
    _create_skill(skills_dir, "code-review", "2.1.0")
    _create_rule(rules_dir, "testing-standards", "0.5.0")

    return {
        "agents": agents_dir,
        "skills": skills_dir,
        "rules": rules_dir,
    }


def _create_agent(agents_dir: Path, name: str, version: str) -> Path:
    agent_file = agents_dir / f"{name}.md"
    agent_file.write_text(
        f"---\nname: {name}\nversion: {version}\n"
        f"description: {name} agent\n---\n# {name}\nContent.\n",
        encoding="utf-8",
    )
    return agent_file


def _create_skill(skills_dir: Path, name: str, version: str) -> Path:
    skill_dir = skills_dir / name
    skill_dir.mkdir(exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\nversion: {version}\n"
        f"description: {name} skill\nauthor: test\n---\n# {name}\n",
        encoding="utf-8",
    )
    (skill_dir / "prompt.md").write_text(f"Prompt for {name}.\n", encoding="utf-8")
    return skill_dir


def _create_rule(rules_dir: Path, name: str, version: str) -> Path:
    rule_file = rules_dir / f"{name}.md"
    rule_file.write_text(
        f"---\nname: {name}\nversion: {version}\n"
        f"description: {name} rule\n---\n# {name}\nContent.\n",
        encoding="utf-8",
    )
    return rule_file


# -------------------------------------------------------------------
# Tests: version bump detection
# -------------------------------------------------------------------


class TestVersionBumpDetection:
    def test_detects_agent_version_bump(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog_path = tmp_path / "catalog-hashes.json"

        # Generate initial catalog
        modified = incremental_update(catalog_path, source_dirs)
        assert modified is True
        initial = json.loads(catalog_path.read_text(encoding="utf-8"))
        initial_hash = initial["agents"]["backend-architect"]["contentHash"]

        # Bump agent version
        _create_agent(source_dirs["agents"], "backend-architect", "1.1.0")

        # Run again - should detect the change
        modified = incremental_update(catalog_path, source_dirs)
        assert modified is True
        updated = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert updated["agents"]["backend-architect"]["version"] == "1.1.0"
        assert updated["agents"]["backend-architect"]["contentHash"] != initial_hash

    def test_detects_skill_version_bump(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog_path = tmp_path / "catalog-hashes.json"
        incremental_update(catalog_path, source_dirs)

        # Bump skill version
        _create_skill(source_dirs["skills"], "code-review", "2.2.0")

        modified = incremental_update(catalog_path, source_dirs)
        assert modified is True
        updated = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert updated["skills"]["code-review"]["version"] == "2.2.0"

    def test_detects_rule_version_bump(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog_path = tmp_path / "catalog-hashes.json"
        incremental_update(catalog_path, source_dirs)

        # Bump rule version
        _create_rule(source_dirs["rules"], "testing-standards", "0.6.0")

        modified = incremental_update(catalog_path, source_dirs)
        assert modified is True
        updated = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert updated["rules"]["testing-standards"]["version"] == "0.6.0"


# -------------------------------------------------------------------
# Tests: unchanged hashes preserved
# -------------------------------------------------------------------


class TestUnchangedPreservation:
    def test_no_modification_when_nothing_changed(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog_path = tmp_path / "catalog-hashes.json"

        # Generate initial
        incremental_update(catalog_path, source_dirs)
        initial_content = catalog_path.read_text(encoding="utf-8")
        initial_data = json.loads(initial_content)

        # Run again with no changes
        modified = incremental_update(catalog_path, source_dirs)
        assert modified is False

        # File should be untouched (same content, including generatedAt)
        assert catalog_path.read_text(encoding="utf-8") == initial_content

    def test_unchanged_items_keep_hashes_when_sibling_changes(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog_path = tmp_path / "catalog-hashes.json"
        incremental_update(catalog_path, source_dirs)
        initial = json.loads(catalog_path.read_text(encoding="utf-8"))
        rule_hash_before = initial["rules"]["testing-standards"]["contentHash"]

        # Change only the agent
        _create_agent(source_dirs["agents"], "backend-architect", "2.0.0")
        incremental_update(catalog_path, source_dirs)
        updated = json.loads(catalog_path.read_text(encoding="utf-8"))

        # The unchanged rule should still have the same hash
        assert updated["rules"]["testing-standards"]["contentHash"] == rule_hash_before


# -------------------------------------------------------------------
# Tests: deleted items
# -------------------------------------------------------------------


class TestDeletedItems:
    def test_removes_deleted_agent(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog_path = tmp_path / "catalog-hashes.json"
        incremental_update(catalog_path, source_dirs)

        # Delete the agent file
        (source_dirs["agents"] / "backend-architect.md").unlink()

        modified = incremental_update(catalog_path, source_dirs)
        assert modified is True
        updated = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert "backend-architect" not in updated["agents"]

    def test_removes_deleted_skill(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog_path = tmp_path / "catalog-hashes.json"
        incremental_update(catalog_path, source_dirs)

        # Delete the skill directory
        shutil.rmtree(source_dirs["skills"] / "code-review")

        modified = incremental_update(catalog_path, source_dirs)
        assert modified is True
        updated = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert "code-review" not in updated["skills"]


# -------------------------------------------------------------------
# Tests: creation from scratch
# -------------------------------------------------------------------


class TestCreationFromScratch:
    def test_creates_file_when_missing(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog_path = tmp_path / "output" / "catalog-hashes.json"
        assert not catalog_path.exists()

        modified = incremental_update(catalog_path, source_dirs)
        assert modified is True
        assert catalog_path.exists()

        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert "backend-architect" in data["agents"]
        assert "code-review" in data["skills"]
        assert "testing-standards" in data["rules"]

    def test_creates_with_correct_structure(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog_path = tmp_path / "catalog-hashes.json"
        incremental_update(catalog_path, source_dirs)

        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert "generatedAt" in data
        assert "aecVersion" in data
        assert "agents" in data
        assert "skills" in data
        assert "rules" in data


# -------------------------------------------------------------------
# Tests: idempotency
# -------------------------------------------------------------------


class TestIdempotency:
    def test_running_twice_produces_same_result(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog_path = tmp_path / "catalog-hashes.json"

        # First run
        incremental_update(catalog_path, source_dirs)
        first_data = json.loads(catalog_path.read_text(encoding="utf-8"))

        # Second run - should detect no changes
        modified = incremental_update(catalog_path, source_dirs)
        assert modified is False

        # Content unchanged
        second_data = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert first_data == second_data

    def test_idempotent_after_version_bump(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog_path = tmp_path / "catalog-hashes.json"
        incremental_update(catalog_path, source_dirs)

        # Bump version
        _create_agent(source_dirs["agents"], "backend-architect", "3.0.0")

        # First update after bump
        incremental_update(catalog_path, source_dirs)
        after_bump = json.loads(catalog_path.read_text(encoding="utf-8"))

        # Second update - should be no-op
        modified = incremental_update(catalog_path, source_dirs)
        assert modified is False
        after_second = json.loads(catalog_path.read_text(encoding="utf-8"))
        assert after_bump == after_second


# -------------------------------------------------------------------
# Tests: content hash accuracy
# -------------------------------------------------------------------


class TestContentHashAccuracy:
    def test_agent_hash_matches_hash_single_file(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog_path = tmp_path / "catalog-hashes.json"
        incremental_update(catalog_path, source_dirs)

        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        agent_path = source_dirs["agents"] / "backend-architect.md"
        expected = hash_single_file(agent_path)
        assert data["agents"]["backend-architect"]["contentHash"] == expected

    def test_skill_hash_matches_hash_skill_directory(
        self, tmp_path: Path, source_dirs: dict
    ) -> None:
        catalog_path = tmp_path / "catalog-hashes.json"
        incremental_update(catalog_path, source_dirs)

        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        skill_path = source_dirs["skills"] / "code-review"
        expected = hash_skill_directory(skill_path)
        assert data["skills"]["code-review"]["contentHash"] == expected
