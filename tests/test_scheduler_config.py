"""Tests for aec.lib.scheduler_config module."""

import json
from pathlib import Path


class TestCreateDefaultConfig:
    """Tests for create_default_config."""

    def test_returns_correct_structure(self):
        """Default config has all required top-level keys."""
        from aec.lib.scheduler_config import create_default_config

        config = create_default_config()
        assert "version" in config
        assert "schedule" in config
        assert "execution" in config
        assert "retention" in config
        assert "last_run" in config

    def test_version_is_1_0_0(self):
        """Default config version is 1.0.0."""
        from aec.lib.scheduler_config import create_default_config

        config = create_default_config()
        assert config["version"] == "1.0.0"

    def test_schedule_time_is_02_00(self):
        """Default schedule time is 02:00."""
        from aec.lib.scheduler_config import create_default_config

        config = create_default_config()
        assert config["schedule"]["time"] == "02:00"

    def test_last_run_is_none(self):
        """Default last_run is None."""
        from aec.lib.scheduler_config import create_default_config

        config = create_default_config()
        assert config["last_run"] is None


class TestLoadSchedulerConfig:
    """Tests for load_scheduler_config."""

    def test_returns_default_when_file_missing(self, temp_dir: Path):
        """Loading from nonexistent path returns default config."""
        from aec.lib.scheduler_config import create_default_config, load_scheduler_config

        config_path = temp_dir / "nonexistent" / "scheduler-config.json"
        config = load_scheduler_config(config_path)
        assert config == create_default_config()

    def test_handles_corrupt_json(self, temp_dir: Path):
        """Loading corrupt JSON returns default config."""
        from aec.lib.scheduler_config import create_default_config, load_scheduler_config

        config_path = temp_dir / "scheduler-config.json"
        config_path.write_text("{not valid json!!!")
        config = load_scheduler_config(config_path)
        assert config == create_default_config()

    def test_fills_missing_keys_via_setdefault(self, temp_dir: Path):
        """Loading config with missing keys fills them with defaults."""
        from aec.lib.scheduler_config import load_scheduler_config

        config_path = temp_dir / "scheduler-config.json"
        # Write a partial config — missing execution and retention
        partial = {"version": "1.0.0", "schedule": {"enabled": False}}
        config_path.write_text(json.dumps(partial))

        config = load_scheduler_config(config_path)
        # Preserved the existing value
        assert config["schedule"]["enabled"] is False
        # Filled in missing sub-keys
        assert config["schedule"]["time"] == "02:00"
        # Filled in missing top-level sections
        assert "execution" in config
        assert "retention" in config
        assert config["last_run"] is None


class TestSaveSchedulerConfig:
    """Tests for save_scheduler_config."""

    def test_creates_file(self, temp_dir: Path):
        """save_scheduler_config writes the file to disk."""
        from aec.lib.scheduler_config import create_default_config, save_scheduler_config

        config_path = temp_dir / "subdir" / "scheduler-config.json"
        save_scheduler_config(create_default_config(), config_path)
        assert config_path.exists()

    def test_round_trip_preserves_data(self, temp_dir: Path):
        """Saving then loading preserves all config data."""
        from aec.lib.scheduler_config import (
            create_default_config,
            load_scheduler_config,
            save_scheduler_config,
        )

        config_path = temp_dir / "scheduler-config.json"
        original = create_default_config()
        original["schedule"]["time"] = "05:30"

        save_scheduler_config(original, config_path)
        loaded = load_scheduler_config(config_path)
        assert loaded == original


class TestUpdateLastRun:
    """Tests for update_last_run."""

    def test_sets_timestamp_and_stats(self):
        """update_last_run populates last_run with timestamp and stats."""
        from aec.lib.scheduler_config import create_default_config, update_last_run

        config = create_default_config()
        result = update_last_run(config, projects_run=3, suites_passed=10, suites_failed=1, suites_skipped=2, seed=42)

        assert result["last_run"] is not None
        assert "timestamp" in result["last_run"]
        assert result["last_run"]["projects_run"] == 3
        assert result["last_run"]["suites_passed"] == 10
        assert result["last_run"]["suites_failed"] == 1
        assert result["last_run"]["suites_skipped"] == 2
        assert result["last_run"]["seed"] == 42

    def test_overwrites_previous_last_run(self):
        """Calling update_last_run twice overwrites the previous value."""
        from aec.lib.scheduler_config import create_default_config, update_last_run

        config = create_default_config()
        update_last_run(config, projects_run=1, suites_passed=1, suites_failed=0, suites_skipped=0, seed=1)

        update_last_run(config, projects_run=2, suites_passed=5, suites_failed=3, suites_skipped=0, seed=99)
        assert config["last_run"]["projects_run"] == 2
        assert config["last_run"]["seed"] == 99


class TestUpdateParallelizationPlan:
    """Tests for update_parallelization_plan."""

    def test_sets_lanes_and_metadata(self):
        """update_parallelization_plan sets lanes and based_on_runs."""
        from aec.lib.scheduler_config import create_default_config, update_parallelization_plan

        config = create_default_config()
        lanes = [["project-a", "project-b"], ["project-c"]]
        result = update_parallelization_plan(config, lanes=lanes, based_on_runs=5)

        plan = result["execution"]["parallelization_plan"]
        assert plan["lanes"] == lanes
        assert plan["based_on_runs"] == 5

    def test_sets_computed_at_timestamp(self):
        """update_parallelization_plan sets a computed_at timestamp."""
        from aec.lib.scheduler_config import create_default_config, update_parallelization_plan

        config = create_default_config()
        result = update_parallelization_plan(config, lanes=[], based_on_runs=0)

        plan = result["execution"]["parallelization_plan"]
        assert "computed_at" in plan
        # Verify ISO format with Z suffix
        assert plan["computed_at"].endswith("Z")


class TestGetScheduleTime:
    """Tests for get_schedule_time."""

    def test_parses_02_00(self):
        """Parses '02:00' into (2, 0)."""
        from aec.lib.scheduler_config import get_schedule_time

        config = {"schedule": {"time": "02:00"}}
        assert get_schedule_time(config) == (2, 0)

    def test_parses_14_30(self):
        """Parses '14:30' into (14, 30)."""
        from aec.lib.scheduler_config import get_schedule_time

        config = {"schedule": {"time": "14:30"}}
        assert get_schedule_time(config) == (14, 30)


class TestIsScheduleEnabled:
    """Tests for is_schedule_enabled."""

    def test_returns_true_when_enabled(self):
        """Returns True when schedule.enabled is True."""
        from aec.lib.scheduler_config import is_schedule_enabled

        config = {"schedule": {"enabled": True}}
        assert is_schedule_enabled(config) is True

    def test_returns_false_when_disabled(self):
        """Returns False when schedule.enabled is False."""
        from aec.lib.scheduler_config import is_schedule_enabled

        config = {"schedule": {"enabled": False}}
        assert is_schedule_enabled(config) is False


class TestGetRetentionConfig:
    """Tests for get_retention_config."""

    def test_returns_retention_section(self):
        """Returns the retention dict from config."""
        from aec.lib.scheduler_config import create_default_config, get_retention_config

        config = create_default_config()
        retention = get_retention_config(config)
        assert retention["report_mode"] == "auto"
        assert retention["report_days"] == 30
        assert retention["profile_days"] == 90


class TestGetExecutionConfig:
    """Tests for get_execution_config."""

    def test_returns_execution_section(self):
        """Returns the execution dict from config."""
        from aec.lib.scheduler_config import create_default_config, get_execution_config

        config = create_default_config()
        execution = get_execution_config(config)
        assert execution["mode"] == "sequential"
        assert execution["randomize_order"] is True
        assert execution["parallel_enabled"] is False
