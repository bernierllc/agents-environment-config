"""Tests for the .aec.json library module (aec/lib/aec_json.py)."""

import json
from pathlib import Path

import pytest

from aec.lib.aec_json import (
    AEC_JSON_FILENAME,
    AEC_JSON_SCHEMA_VERSION,
    create_skeleton,
    load_aec_json,
    save_aec_json,
    aec_json_exists,
    update_ports_section,
    update_test_section,
    update_installed_section,
    manage_aec_json_gitignore,
)


class TestConstants:
    """Verify module-level constants."""

    def test_filename_constant(self):
        """AEC_JSON_FILENAME must be '.aec.json'."""
        assert AEC_JSON_FILENAME == ".aec.json"

    def test_schema_version_constant(self):
        """AEC_JSON_SCHEMA_VERSION must be '1.0.0'."""
        assert AEC_JSON_SCHEMA_VERSION == "1.0.0"


class TestCreateSkeleton:
    """Tests for create_skeleton()."""

    def test_returns_correct_structure(self):
        """Skeleton must contain all required top-level keys."""
        result = create_skeleton("my-project")
        assert "$schema" in result
        assert "version" in result
        assert "project" in result
        assert "ports" in result
        assert "test" in result
        assert "installed" in result

    def test_uses_provided_project_name(self):
        """project.name must match the provided argument."""
        result = create_skeleton("acme-app")
        assert result["project"]["name"] == "acme-app"

    def test_default_description_is_empty(self):
        """project.description defaults to empty string."""
        result = create_skeleton("acme-app")
        assert result["project"]["description"] == ""

    def test_with_description(self):
        """project.description is set when provided."""
        result = create_skeleton("acme-app", description="A cool project")
        assert result["project"]["description"] == "A cool project"

    def test_schema_url(self):
        """$schema must point to the expected URL."""
        result = create_skeleton("x")
        assert result["$schema"] == "https://aec.bernier.dev/schema/aec.json"

    def test_version_matches_constant(self):
        """version field must match AEC_JSON_SCHEMA_VERSION."""
        result = create_skeleton("x")
        assert result["version"] == AEC_JSON_SCHEMA_VERSION

    def test_test_section_structure(self):
        """test section must have suites, prerequisites, and scheduled."""
        result = create_skeleton("x")
        assert result["test"] == {"suites": {}, "prerequisites": [], "scheduled": []}

    def test_installed_section_structure(self):
        """installed section must have skills, rules, and agents."""
        result = create_skeleton("x")
        assert result["installed"] == {"skills": {}, "rules": {}, "agents": {}}


class TestLoadSaveRoundTrip:
    """Tests for load_aec_json(), save_aec_json(), and aec_json_exists()."""

    def test_load_returns_none_when_missing(self, temp_dir: Path):
        """load_aec_json returns None when no .aec.json exists."""
        assert load_aec_json(temp_dir) is None

    def test_aec_json_exists_false(self, temp_dir: Path):
        """aec_json_exists returns False when file is missing."""
        assert aec_json_exists(temp_dir) is False

    def test_save_creates_file(self, temp_dir: Path):
        """save_aec_json creates the .aec.json file."""
        data = create_skeleton("test-proj")
        save_aec_json(temp_dir, data)
        assert (temp_dir / AEC_JSON_FILENAME).exists()

    def test_aec_json_exists_true(self, temp_dir: Path):
        """aec_json_exists returns True after saving."""
        save_aec_json(temp_dir, create_skeleton("test-proj"))
        assert aec_json_exists(temp_dir) is True

    def test_round_trip_preserves_data(self, temp_dir: Path):
        """save then load returns identical data."""
        original = create_skeleton("round-trip")
        original["ports"] = {"web": 3000, "api": 8080}
        save_aec_json(temp_dir, original)
        loaded = load_aec_json(temp_dir)
        assert loaded == original

    def test_round_trip_preserves_unknown_keys(self, temp_dir: Path):
        """Unknown keys added by the user are preserved through save/load."""
        data = create_skeleton("extended")
        data["custom_field"] = {"foo": "bar"}
        data["another_extra"] = [1, 2, 3]
        save_aec_json(temp_dir, data)
        loaded = load_aec_json(temp_dir)
        assert loaded["custom_field"] == {"foo": "bar"}
        assert loaded["another_extra"] == [1, 2, 3]

    def test_load_corrupt_json_returns_skeleton(self, temp_dir: Path):
        """Corrupt JSON returns a default skeleton and logs a warning."""
        filepath = temp_dir / AEC_JSON_FILENAME
        filepath.write_text("{this is not valid json", encoding="utf-8")
        result = load_aec_json(temp_dir)
        assert result is not None
        assert "project" in result
        assert result["project"]["name"] == temp_dir.name

    def test_save_writes_pretty_json(self, temp_dir: Path):
        """Saved file uses indent=2 formatting."""
        data = create_skeleton("pretty")
        save_aec_json(temp_dir, data)
        text = (temp_dir / AEC_JSON_FILENAME).read_text(encoding="utf-8")
        # indent=2 means nested keys are indented
        assert '  "version"' in text
        # File ends with newline
        assert text.endswith("\n")


class TestUpdatePorts:
    """Tests for update_ports_section()."""

    def test_adds_new_ports(self):
        """New port entries are added."""
        data = create_skeleton("x")
        result = update_ports_section(data, {"web": 3000})
        assert result["ports"]["web"] == 3000

    def test_merges_without_removing_existing(self):
        """Existing ports are preserved when adding new ones."""
        data = create_skeleton("x")
        data["ports"] = {"web": 3000}
        result = update_ports_section(data, {"api": 8080})
        assert result["ports"]["web"] == 3000
        assert result["ports"]["api"] == 8080

    def test_overwrites_existing_port(self):
        """An existing port value can be updated."""
        data = create_skeleton("x")
        data["ports"] = {"web": 3000}
        result = update_ports_section(data, {"web": 4000})
        assert result["ports"]["web"] == 4000


class TestUpdateTest:
    """Tests for update_test_section()."""

    def test_updates_suites_only(self):
        """Updating suites does not change prerequisites or scheduled."""
        data = create_skeleton("x")
        data["test"]["prerequisites"] = ["docker"]
        result = update_test_section(data, suites={"unit": {"cmd": "pytest"}})
        assert result["test"]["suites"] == {"unit": {"cmd": "pytest"}}
        assert result["test"]["prerequisites"] == ["docker"]

    def test_updates_prerequisites_only(self):
        """Updating prerequisites does not change suites or scheduled."""
        data = create_skeleton("x")
        data["test"]["suites"] = {"unit": {"cmd": "pytest"}}
        result = update_test_section(data, prerequisites=["node", "docker"])
        assert result["test"]["prerequisites"] == ["node", "docker"]
        assert result["test"]["suites"] == {"unit": {"cmd": "pytest"}}

    def test_updates_scheduled_only(self):
        """Updating scheduled does not change suites or prerequisites."""
        data = create_skeleton("x")
        result = update_test_section(data, scheduled=["nightly"])
        assert result["test"]["scheduled"] == ["nightly"]
        assert result["test"]["suites"] == {}

    def test_none_args_leave_fields_unchanged(self):
        """Passing None for all args leaves the test section unchanged."""
        data = create_skeleton("x")
        data["test"]["suites"] = {"e2e": {"cmd": "cypress"}}
        result = update_test_section(data)
        assert result["test"]["suites"] == {"e2e": {"cmd": "cypress"}}


class TestUpdateInstalled:
    """Tests for update_installed_section()."""

    def test_replaces_wholesale(self):
        """installed section is fully replaced."""
        data = create_skeleton("x")
        data["installed"]["skills"] = {"old-skill": {"version": "1.0"}}
        new_installed = {"skills": {"new-skill": {"version": "2.0"}}, "rules": {}, "agents": {}}
        result = update_installed_section(data, new_installed)
        assert result["installed"] == new_installed
        assert "old-skill" not in result["installed"]["skills"]

    def test_returns_same_dict(self):
        """The function mutates and returns the same dict object."""
        data = create_skeleton("x")
        result = update_installed_section(data, {"skills": {}, "rules": {}, "agents": {}})
        assert result is data


class TestManageGitignore:
    """Tests for manage_aec_json_gitignore()."""

    def test_adds_to_existing_gitignore(self, temp_dir: Path):
        """Adds .aec.json to an existing .gitignore."""
        (temp_dir / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        result = manage_aec_json_gitignore(temp_dir, should_ignore=True)
        assert result == "added"
        text = (temp_dir / ".gitignore").read_text(encoding="utf-8")
        assert ".aec.json" in text
        assert "node_modules/" in text

    def test_creates_gitignore_when_missing(self, temp_dir: Path):
        """Creates .gitignore with .aec.json when file doesn't exist and should_ignore=True."""
        result = manage_aec_json_gitignore(temp_dir, should_ignore=True)
        assert result == "added"
        text = (temp_dir / ".gitignore").read_text(encoding="utf-8")
        assert ".aec.json" in text

    def test_removes_from_gitignore(self, temp_dir: Path):
        """Removes .aec.json from .gitignore."""
        (temp_dir / ".gitignore").write_text("node_modules/\n.aec.json\n.env\n", encoding="utf-8")
        result = manage_aec_json_gitignore(temp_dir, should_ignore=False)
        assert result == "removed"
        text = (temp_dir / ".gitignore").read_text(encoding="utf-8")
        assert ".aec.json" not in text
        assert "node_modules/" in text
        assert ".env" in text

    def test_already_ignored(self, temp_dir: Path):
        """Returns 'already_ignored' when .aec.json is already in .gitignore."""
        (temp_dir / ".gitignore").write_text(".aec.json\n", encoding="utf-8")
        result = manage_aec_json_gitignore(temp_dir, should_ignore=True)
        assert result == "already_ignored"

    def test_already_tracked(self, temp_dir: Path):
        """Returns 'already_tracked' when .aec.json is not in .gitignore and should_ignore=False."""
        (temp_dir / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        result = manage_aec_json_gitignore(temp_dir, should_ignore=False)
        assert result == "already_tracked"

    def test_no_gitignore(self, temp_dir: Path):
        """Returns 'no_gitignore' when .gitignore doesn't exist and should_ignore=False."""
        result = manage_aec_json_gitignore(temp_dir, should_ignore=False)
        assert result == "no_gitignore"

    def test_handles_commented_entry(self, temp_dir: Path):
        """An entry with a trailing comment is still detected as ignored."""
        (temp_dir / ".gitignore").write_text(".aec.json # project config\n", encoding="utf-8")
        result = manage_aec_json_gitignore(temp_dir, should_ignore=True)
        assert result == "already_ignored"

    def test_removes_commented_entry(self, temp_dir: Path):
        """An entry with a trailing comment is removed correctly."""
        (temp_dir / ".gitignore").write_text("other\n.aec.json # project config\nmore\n", encoding="utf-8")
        result = manage_aec_json_gitignore(temp_dir, should_ignore=False)
        assert result == "removed"
        text = (temp_dir / ".gitignore").read_text(encoding="utf-8")
        assert ".aec.json" not in text
        assert "other" in text
        assert "more" in text
