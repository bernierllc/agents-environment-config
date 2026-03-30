"""Tests for aec skills CLI commands."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


def _make_skill(parent: Path, name: str, version: str = "1.0.0") -> Path:
    """Helper to create a skill directory with SKILL.md."""
    skill_dir = parent / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Test {name}\nversion: {version}\nauthor: Test\n---\n# {name}\n"
    )
    return skill_dir


class TestListSkills:
    """Test aec skills list command."""

    def test_shows_available_and_installed(self, temp_dir: Path, capsys):
        # Setup source with 2 skills
        source = temp_dir / "source"
        source.mkdir()
        _make_skill(source, "skill-a", "1.0.0")
        _make_skill(source, "skill-b", "2.0.0")

        # Setup installed with 1 skill
        installed_dir = temp_dir / "installed"
        installed_dir.mkdir()
        _make_skill(installed_dir, "skill-a", "1.0.0")

        manifest_path = temp_dir / "installed-skills.json"
        manifest_path.write_text(json.dumps({
            "manifestVersion": 1,
            "installedAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "skills": {
                "skill-a": {
                    "version": "1.0.0",
                    "contentHash": "sha256:abc",
                    "installedAt": "2026-01-01T00:00:00Z",
                    "source": "agents-environment-config",
                }
            },
        }))

        from aec.commands.skills import list_skills

        list_skills(
            source_dir=source,
            installed_dir=installed_dir,
            manifest_path=manifest_path,
        )
        output = capsys.readouterr().out
        assert "skill-a" in output
        assert "skill-b" in output
        assert "up to date" in output
        assert "available" in output


class TestInstallSkills:
    """Test aec skills install command."""

    def test_copies_skill_to_installed_dir(self, temp_dir: Path):
        source = temp_dir / "source"
        source.mkdir()
        _make_skill(source, "new-skill", "1.0.0")

        installed_dir = temp_dir / "installed"
        installed_dir.mkdir()

        manifest_path = temp_dir / "installed-skills.json"

        from aec.commands.skills import install_skills

        install_skills(
            names=["new-skill"],
            source_dir=source,
            installed_dir=installed_dir,
            manifest_path=manifest_path,
            yes=True,
        )

        assert (installed_dir / "new-skill" / "SKILL.md").exists()

        manifest = json.loads(manifest_path.read_text())
        assert "new-skill" in manifest["skills"]
        assert manifest["skills"]["new-skill"]["version"] == "1.0.0"

    def test_errors_on_unknown_skill(self, temp_dir: Path):
        source = temp_dir / "source"
        source.mkdir()
        installed_dir = temp_dir / "installed"
        installed_dir.mkdir()
        manifest_path = temp_dir / "installed-skills.json"

        from aec.commands.skills import install_skills

        with pytest.raises(SystemExit):
            install_skills(
                names=["nonexistent"],
                source_dir=source,
                installed_dir=installed_dir,
                manifest_path=manifest_path,
                yes=True,
            )


class TestUninstallSkills:
    """Test aec skills uninstall command."""

    def test_removes_skill_directory_and_manifest_entry(self, temp_dir: Path):
        installed_dir = temp_dir / "installed"
        installed_dir.mkdir()
        _make_skill(installed_dir, "old-skill", "1.0.0")

        manifest_path = temp_dir / "installed-skills.json"
        manifest_path.write_text(json.dumps({
            "manifestVersion": 1,
            "installedAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "skills": {
                "old-skill": {
                    "version": "1.0.0",
                    "contentHash": "sha256:abc",
                    "installedAt": "2026-01-01T00:00:00Z",
                    "source": "agents-environment-config",
                }
            },
        }))

        from aec.commands.skills import uninstall_skills

        uninstall_skills(
            names=["old-skill"],
            installed_dir=installed_dir,
            manifest_path=manifest_path,
            yes=True,
        )

        assert not (installed_dir / "old-skill").exists()
        manifest = json.loads(manifest_path.read_text())
        assert "old-skill" not in manifest["skills"]


class TestUpdateSkills:
    """Test aec skills update command."""

    def test_updates_skill_with_newer_version(self, temp_dir: Path):
        source = temp_dir / "source"
        source.mkdir()
        _make_skill(source, "my-skill", "2.0.0")

        installed_dir = temp_dir / "installed"
        installed_dir.mkdir()
        _make_skill(installed_dir, "my-skill", "1.0.0")

        manifest_path = temp_dir / "installed-skills.json"
        manifest_path.write_text(json.dumps({
            "manifestVersion": 1,
            "installedAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "skills": {
                "my-skill": {
                    "version": "1.0.0",
                    "contentHash": "sha256:abc",
                    "installedAt": "2026-01-01T00:00:00Z",
                    "source": "agents-environment-config",
                }
            },
        }))

        from aec.commands.skills import update_skills

        update_skills(
            names=None,
            source_dir=source,
            installed_dir=installed_dir,
            manifest_path=manifest_path,
            yes=True,
        )

        manifest = json.loads(manifest_path.read_text())
        assert manifest["skills"]["my-skill"]["version"] == "2.0.0"

    def test_reports_no_updates_when_current(self, temp_dir: Path, capsys):
        source = temp_dir / "source"
        source.mkdir()
        _make_skill(source, "my-skill", "1.0.0")

        installed_dir = temp_dir / "installed"
        installed_dir.mkdir()
        _make_skill(installed_dir, "my-skill", "1.0.0")

        manifest_path = temp_dir / "installed-skills.json"
        manifest_path.write_text(json.dumps({
            "manifestVersion": 1,
            "installedAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "skills": {
                "my-skill": {
                    "version": "1.0.0",
                    "contentHash": "sha256:abc",
                    "installedAt": "2026-01-01T00:00:00Z",
                    "source": "agents-environment-config",
                }
            },
        }))

        from aec.commands.skills import update_skills

        update_skills(
            names=None,
            source_dir=source,
            installed_dir=installed_dir,
            manifest_path=manifest_path,
            yes=True,
        )
        output = capsys.readouterr().out
        assert "up to date" in output.lower()


class TestParseSelection:
    """Test range/selection parsing for skill install prompt."""

    def test_parse_all(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("a", 10) == set(range(1, 11))
        assert _parse_selection("all", 10) == set(range(1, 11))

    def test_parse_none(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("n", 10) == set()
        assert _parse_selection("none", 10) == set()

    def test_parse_single_numbers(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("1,3,5", 10) == {1, 3, 5}

    def test_parse_ranges(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("1-3,7", 10) == {1, 2, 3, 7}

    def test_parse_mixed(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("1,3-5,8", 10) == {1, 3, 4, 5, 8}

    def test_ignores_out_of_range(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("1,99", 5) == {1}

    def test_empty_input_returns_empty(self):
        from aec.commands.skills import _parse_selection

        assert _parse_selection("", 10) == set()
