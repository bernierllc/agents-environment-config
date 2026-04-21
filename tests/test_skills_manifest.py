"""Tests for skills manifest library."""

import json
import tempfile
from pathlib import Path

import pytest


class TestParseSkillFrontmatter:
    """Test SKILL.md frontmatter parsing."""

    def test_parses_complete_frontmatter(self, temp_dir: Path):
        skill_dir = temp_dir / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: my-skill\n"
            "description: A test skill\n"
            "version: 1.2.3\n"
            "author: Test Author\n"
            "---\n"
            "# My Skill\n"
            "Instructions here.\n"
        )
        from aec.lib.skills_manifest import parse_skill_frontmatter

        result = parse_skill_frontmatter(skill_dir)
        assert result["name"] == "my-skill"
        assert result["description"] == "A test skill"
        assert result["version"] == "1.2.3"
        assert result["author"] == "Test Author"

    def test_missing_version_defaults_to_0_0_0(self, temp_dir: Path):
        skill_dir = temp_dir / "old-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: old-skill\n"
            "description: No version field\n"
            "---\n"
            "# Old Skill\n"
        )
        from aec.lib.skills_manifest import parse_skill_frontmatter

        result = parse_skill_frontmatter(skill_dir)
        assert result["version"] == "0.0.0"

    def test_no_skill_md_returns_none(self, temp_dir: Path):
        skill_dir = temp_dir / "empty"
        skill_dir.mkdir()
        from aec.lib.skills_manifest import parse_skill_frontmatter

        result = parse_skill_frontmatter(skill_dir)
        assert result is None

    def test_invalid_frontmatter_returns_none(self, temp_dir: Path):
        skill_dir = temp_dir / "bad"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("No frontmatter here")
        from aec.lib.skills_manifest import parse_skill_frontmatter

        result = parse_skill_frontmatter(skill_dir)
        assert result is None


class TestVersionComparison:
    """Test semver comparison."""

    def test_parse_version(self):
        from aec.lib.skills_manifest import parse_version

        assert parse_version("1.2.3") == (1, 2, 3)
        assert parse_version("0.0.0") == (0, 0, 0)
        assert parse_version("10.20.30") == (10, 20, 30)

    def test_version_is_newer(self):
        from aec.lib.skills_manifest import version_is_newer

        assert version_is_newer("1.1.0", "1.0.0") is True
        assert version_is_newer("2.0.0", "1.9.9") is True
        assert version_is_newer("1.0.1", "1.0.0") is True
        assert version_is_newer("1.0.0", "1.0.0") is False
        assert version_is_newer("0.9.0", "1.0.0") is False


class TestContentHashing:
    """Test skill directory hashing."""

    def test_hash_produces_sha256_prefix(self, temp_dir: Path):
        skill_dir = temp_dir / "hashtest"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test")
        from aec.lib.skills_manifest import hash_skill_directory

        result = hash_skill_directory(skill_dir)
        assert result.startswith("sha256:")

    def test_hash_ignores_hidden_files(self, temp_dir: Path):
        skill_dir = temp_dir / "hashtest2"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test")
        from aec.lib.skills_manifest import hash_skill_directory

        hash_before = hash_skill_directory(skill_dir)
        (skill_dir / ".DS_Store").write_text("junk")
        hash_after = hash_skill_directory(skill_dir)
        assert hash_before == hash_after

    def test_hash_changes_on_content_change(self, temp_dir: Path):
        skill_dir = temp_dir / "hashtest3"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test")
        from aec.lib.skills_manifest import hash_skill_directory

        hash_before = hash_skill_directory(skill_dir)
        (skill_dir / "SKILL.md").write_text("# Changed")
        hash_after = hash_skill_directory(skill_dir)
        assert hash_before != hash_after

    def test_hash_includes_subdirectory_files(self, temp_dir: Path):
        skill_dir = temp_dir / "hashtest4"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test")
        from aec.lib.skills_manifest import hash_skill_directory

        hash_before = hash_skill_directory(skill_dir)
        refs = skill_dir / "references"
        refs.mkdir()
        (refs / "guide.md").write_text("Guide content")
        hash_after = hash_skill_directory(skill_dir)
        assert hash_before != hash_after


class TestManifestIO:
    """Test installed-skills.json read/write."""

    def test_load_empty_manifest(self, temp_dir: Path):
        from aec.lib.skills_manifest import load_installed_manifest

        result = load_installed_manifest(temp_dir / "nonexistent.json")
        assert result["manifestVersion"] == 1
        assert result["skills"] == {}

    def test_save_and_load_manifest(self, temp_dir: Path):
        manifest_path = temp_dir / "installed-skills.json"
        from aec.lib.skills_manifest import (
            load_installed_manifest,
            save_installed_manifest,
        )

        manifest = load_installed_manifest(manifest_path)
        manifest["skills"]["test-skill"] = {
            "version": "1.0.0",
            "contentHash": "sha256:abc123",
            "installedAt": "2026-03-30T14:00:00Z",
            "source": "agents-environment-config",
        }
        save_installed_manifest(manifest, manifest_path)

        reloaded = load_installed_manifest(manifest_path)
        assert "test-skill" in reloaded["skills"]
        assert reloaded["skills"]["test-skill"]["version"] == "1.0.0"

    def test_load_corrupt_manifest_returns_empty(self, temp_dir: Path):
        manifest_path = temp_dir / "installed-skills.json"
        manifest_path.write_text("not valid json{{{")
        from aec.lib.skills_manifest import load_installed_manifest

        result = load_installed_manifest(manifest_path)
        assert result["skills"] == {}


class TestDiscoverAvailableSkills:
    """Test skill discovery from source directory."""

    def test_discovers_top_level_skills(self, temp_dir: Path):
        source = temp_dir / "skills-source"
        source.mkdir()
        skill_a = source / "skill-a"
        skill_a.mkdir()
        (skill_a / "SKILL.md").write_text(
            "---\nname: skill-a\ndescription: Skill A\nversion: 1.0.0\n---\n"
        )
        from aec.lib.skills_manifest import discover_available_skills

        result = discover_available_skills(source)
        assert "skill-a" in result
        assert result["skill-a"]["version"] == "1.0.0"
        assert result["skill-a"]["path"] == "skill-a"

    def test_discovers_nested_skills(self, temp_dir: Path):
        source = temp_dir / "skills-source"
        source.mkdir()
        group = source / "document-skills"
        group.mkdir()
        docx = group / "docx"
        docx.mkdir()
        (docx / "SKILL.md").write_text(
            "---\nname: docx\ndescription: Word docs\nversion: 1.0.0\n---\n"
        )
        from aec.lib.skills_manifest import discover_available_skills

        result = discover_available_skills(source)
        assert "docx" in result
        assert result["docx"]["path"] == "document-skills/docx"

    def test_skips_non_skill_directories(self, temp_dir: Path):
        source = temp_dir / "skills-source"
        source.mkdir()
        (source / "scripts").mkdir()
        (source / "assets").mkdir()
        (source / "README.md").write_text("# README")
        from aec.lib.skills_manifest import discover_available_skills

        result = discover_available_skills(source)
        assert result == {}

    def test_uses_manifest_json_when_available(self, temp_dir: Path):
        source = temp_dir / "skills-source"
        source.mkdir()
        manifest = {
            "manifestVersion": 1,
            "generatedAt": "2026-03-30T12:00:00Z",
            "skills": {
                "my-skill": {
                    "version": "2.0.0",
                    "description": "From manifest",
                    "author": "Test",
                    "path": "my-skill",
                }
            },
        }
        (source / "skills-manifest.json").write_text(json.dumps(manifest))
        from aec.lib.skills_manifest import discover_available_skills

        result = discover_available_skills(source)
        assert result["my-skill"]["version"] == "2.0.0"

    def test_skill_md_overrides_stale_manifest_version(self, temp_dir: Path):
        """SKILL.md frontmatter wins over skills-manifest.json for the same skill."""
        source = temp_dir / "skills-source"
        source.mkdir()
        my_skill = source / "my-skill"
        my_skill.mkdir()
        (my_skill / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: From file\nversion: 3.0.0\nauthor: File\n---\n"
        )
        manifest = {
            "manifestVersion": 1,
            "generatedAt": "2026-03-30T12:00:00Z",
            "skills": {
                "my-skill": {
                    "version": "1.0.0",
                    "description": "Stale manifest",
                    "author": "Manifest",
                    "path": "my-skill",
                }
            },
        }
        (source / "skills-manifest.json").write_text(json.dumps(manifest))
        from aec.lib.skills_manifest import discover_available_skills

        result = discover_available_skills(source)
        assert result["my-skill"]["version"] == "3.0.0"
        assert result["my-skill"]["description"] == "From file"
        assert result["my-skill"]["author"] == "File"


class TestPlanSkillDirectoryReplace:
    """Tests for upgrade copy vs manifest-only decisions."""

    def test_sync_manifest_when_trees_match(self, temp_dir: Path):
        from aec.lib.skills_manifest import plan_skill_directory_replace

        src = temp_dir / "src" / "s"
        dst = temp_dir / "dst" / "s"
        for d in (src, dst):
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(
                "---\nname: s\nversion: 2.0.0\ndescription: X\n---\nBody"
            )
        plan = plan_skill_directory_replace(
            dst, src, {"version": "1.0.0", "contentHash": "sha256:old"}, assume_yes=False
        )
        assert plan == "sync_manifest"

    def test_overwrite_when_matches_recorded_baseline(self, temp_dir: Path):
        from aec.lib.skills_manifest import (
            hash_skill_directory,
            plan_skill_directory_replace,
        )

        src = temp_dir / "src" / "s"
        dst = temp_dir / "dst" / "s"
        src.mkdir(parents=True)
        dst.mkdir(parents=True)
        (dst / "SKILL.md").write_text(
            "---\nname: s\nversion: 1.0.0\ndescription: X\n---\nOld"
        )
        (src / "SKILL.md").write_text(
            "---\nname: s\nversion: 2.0.0\ndescription: X\n---\nNew"
        )
        rec = hash_skill_directory(dst)
        plan = plan_skill_directory_replace(
            dst,
            src,
            {"version": "1.0.0", "contentHash": rec},
            assume_yes=False,
        )
        assert plan == "overwrite"

    def test_prompt_when_differs_from_recorded_and_source(self, temp_dir: Path):
        from aec.lib.skills_manifest import plan_skill_directory_replace

        src = temp_dir / "src" / "s"
        dst = temp_dir / "dst" / "s"
        src.mkdir(parents=True)
        dst.mkdir(parents=True)
        (dst / "SKILL.md").write_text(
            "---\nname: s\nversion: 1.0.0\ndescription: X\n---\nEdited"
        )
        (src / "SKILL.md").write_text(
            "---\nname: s\nversion: 2.0.0\ndescription: X\n---\nUpstream"
        )
        plan = plan_skill_directory_replace(
            dst,
            src,
            {"version": "1.0.0", "contentHash": "sha256:fake"},
            assume_yes=False,
        )
        assert plan == "prompt"


class TestManifestRecovery:
    """Test manifest rebuild from installed skills."""

    def test_rebuilds_from_installed_skills(self, temp_dir: Path):
        skills_dir = temp_dir / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill = skills_dir / "my-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: Test\nversion: 1.5.0\n---\n"
        )
        from aec.lib.skills_manifest import rebuild_manifest_from_installed

        manifest = rebuild_manifest_from_installed(skills_dir)
        assert "my-skill" in manifest["skills"]
        assert manifest["skills"]["my-skill"]["version"] == "1.5.0"
        assert manifest["skills"]["my-skill"]["contentHash"].startswith("sha256:")
