"""Tests for per-suite prerequisites in aec_json and Phase 2 config constants."""

from pathlib import Path

from aec.lib.aec_json import (
    create_skeleton,
    get_suite_prerequisites,
    load_aec_json,
    save_aec_json,
    update_suite_prerequisites,
    update_test_section,
)


class TestUpdateSuitePrerequisites:
    """Tests for update_suite_prerequisites()."""

    def test_adds_prerequisites_to_suite(self):
        """Prerequisites are added to an existing suite."""
        data = create_skeleton("x")
        data["test"]["suites"] = {"unit": {"cmd": "pytest"}}
        result = update_suite_prerequisites(data, "unit", ["docker", "node"])
        assert result["test"]["suites"]["unit"]["prerequisites"] == ["docker", "node"]
        # Original keys preserved
        assert result["test"]["suites"]["unit"]["cmd"] == "pytest"

    def test_creates_suite_if_missing(self):
        """Suite is created if it does not exist."""
        data = create_skeleton("x")
        result = update_suite_prerequisites(data, "integration", ["postgres"])
        assert result["test"]["suites"]["integration"] == {"prerequisites": ["postgres"]}

    def test_overwrites_existing_prerequisites(self):
        """Existing prerequisites are replaced, not merged."""
        data = create_skeleton("x")
        data["test"]["suites"] = {"unit": {"prerequisites": ["old"]}}
        result = update_suite_prerequisites(data, "unit", ["new1", "new2"])
        assert result["test"]["suites"]["unit"]["prerequisites"] == ["new1", "new2"]

    def test_returns_same_dict(self):
        """The function mutates and returns the same dict object."""
        data = create_skeleton("x")
        result = update_suite_prerequisites(data, "unit", [])
        assert result is data

    def test_creates_test_section_if_missing(self):
        """test section is created if absent from data."""
        data = {"project": {"name": "bare"}}
        result = update_suite_prerequisites(data, "e2e", ["chrome"])
        assert result["test"]["suites"]["e2e"]["prerequisites"] == ["chrome"]
        assert "prerequisites" in result["test"]
        assert "scheduled" in result["test"]


class TestGetSuitePrerequisites:
    """Tests for get_suite_prerequisites()."""

    def test_returns_prerequisites_for_known_suite(self):
        """Returns the prerequisites list for a known suite."""
        data = create_skeleton("x")
        data["test"]["suites"] = {"unit": {"prerequisites": ["docker"]}}
        assert get_suite_prerequisites(data, "unit") == ["docker"]

    def test_returns_empty_list_for_unknown_suite(self):
        """Returns empty list when suite does not exist."""
        data = create_skeleton("x")
        assert get_suite_prerequisites(data, "nonexistent") == []

    def test_returns_empty_list_when_no_prerequisites_field(self):
        """Returns empty list when suite exists but has no prerequisites key."""
        data = create_skeleton("x")
        data["test"]["suites"] = {"unit": {"cmd": "pytest"}}
        assert get_suite_prerequisites(data, "unit") == []

    def test_returns_empty_list_when_no_test_section(self):
        """Returns empty list when test section is absent."""
        data = {"project": {"name": "bare"}}
        assert get_suite_prerequisites(data, "unit") == []


class TestPrerequisitesRoundTrip:
    """Round-trip persistence tests for per-suite prerequisites."""

    def test_save_and_reload_preserves_prerequisites(self, temp_dir: Path):
        """Per-suite prerequisites survive save/load round-trip."""
        data = create_skeleton("round-trip")
        update_suite_prerequisites(data, "unit", ["docker"])
        update_suite_prerequisites(data, "e2e", ["chrome", "postgres"])
        save_aec_json(temp_dir, data)

        loaded = load_aec_json(temp_dir)
        assert get_suite_prerequisites(loaded, "unit") == ["docker"]
        assert get_suite_prerequisites(loaded, "e2e") == ["chrome", "postgres"]

    def test_update_test_section_preserves_suite_prerequisites(self):
        """update_test_section with suites that include prerequisites preserves them."""
        data = create_skeleton("x")
        suites_with_prereqs = {
            "unit": {"cmd": "pytest", "prerequisites": ["docker"]},
            "e2e": {"cmd": "cypress", "prerequisites": ["chrome"]},
        }
        result = update_test_section(data, suites=suites_with_prereqs)
        assert result["test"]["suites"]["unit"]["prerequisites"] == ["docker"]
        assert result["test"]["suites"]["e2e"]["prerequisites"] == ["chrome"]
        assert result["test"]["suites"]["unit"]["cmd"] == "pytest"


class TestPhase2ConfigConstants:
    """Tests for Phase 2 path constants in config.py."""

    def test_aec_tests_dir_exists(self):
        """AEC_TESTS_DIR constant is defined."""
        from aec.lib.config import AEC_TESTS_DIR
        assert AEC_TESTS_DIR is not None

    def test_aec_profiles_dir_exists(self):
        """AEC_PROFILES_DIR constant is defined."""
        from aec.lib.config import AEC_PROFILES_DIR
        assert AEC_PROFILES_DIR is not None

    def test_aec_scheduler_config_exists(self):
        """AEC_SCHEDULER_CONFIG constant is defined."""
        from aec.lib.config import AEC_SCHEDULER_CONFIG
        assert AEC_SCHEDULER_CONFIG is not None

    def test_aec_runner_script_exists(self):
        """AEC_RUNNER_SCRIPT constant is defined."""
        from aec.lib.config import AEC_RUNNER_SCRIPT
        assert AEC_RUNNER_SCRIPT is not None

    def test_constants_are_path_objects(self):
        """All new constants are Path objects."""
        from aec.lib.config import (
            AEC_TESTS_DIR,
            AEC_PROFILES_DIR,
            AEC_SCHEDULER_CONFIG,
            AEC_RUNNER_SCRIPT,
        )
        assert isinstance(AEC_TESTS_DIR, Path)
        assert isinstance(AEC_PROFILES_DIR, Path)
        assert isinstance(AEC_SCHEDULER_CONFIG, Path)
        assert isinstance(AEC_RUNNER_SCRIPT, Path)

    def test_constants_under_aec_home(self):
        """All new constants are under AEC_HOME."""
        from aec.lib.config import (
            AEC_HOME,
            AEC_TESTS_DIR,
            AEC_PROFILES_DIR,
            AEC_SCHEDULER_CONFIG,
            AEC_RUNNER_SCRIPT,
        )
        for path in [AEC_TESTS_DIR, AEC_PROFILES_DIR, AEC_SCHEDULER_CONFIG, AEC_RUNNER_SCRIPT]:
            assert str(path).startswith(str(AEC_HOME)), f"{path} is not under {AEC_HOME}"
