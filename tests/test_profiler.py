"""Tests for aec.lib.profiler module — system state profiling."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# --- Helpers for monkeypatching subprocess.run ---

def _make_run_mock(stdout: str = "", returncode: int = 0):
    """Create a mock subprocess.run result."""
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    return result


LSOF_OUTPUT = """\
COMMAND   PID   USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
node    12345   matt   22u  IPv4 0x1234      0t0  TCP *:3000 (LISTEN)
node    12346   matt   23u  IPv4 0x1235      0t0  TCP 127.0.0.1:5432 (LISTEN)
postgres 1234   matt   10u  IPv4 0x1236      0t0  TCP *:5433 (LISTEN)
"""

PS_AUX_OUTPUT = """\
USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
matt     12345  1.0  2.0 100000 20000 ?        S    10:00   0:01 node server.js
matt     12346  0.5  1.0  50000 10000 ?        Z    10:01   0:00 defunct
matt     12347  0.3  0.5  30000  5000 ?        D    10:02   0:00 some_io_task
matt     12348  2.0  3.0 200000 30000 ?        S    10:03   0:05 node jest.config.ts
matt     12349  1.5  2.5 150000 25000 ?        S    10:04   0:03 npm run test
"""

DOCKER_PS_OUTPUT = """\
earnlearn-test-db
redis-cache
"""

NETSTAT_WINDOWS_OUTPUT = """\
  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:80             0.0.0.0:0              LISTENING       1234
  TCP    0.0.0.0:443            0.0.0.0:0              LISTENING       5678
  TCP    0.0.0.0:3000           0.0.0.0:0              ESTABLISHED     9999
"""


class TestSnapshotPorts:
    """Test snapshot_ports function."""

    def test_parses_lsof_output(self, monkeypatch):
        """Should parse lsof output to extract listening ports."""
        from aec.lib import profiler

        monkeypatch.setattr(profiler, "IS_WINDOWS", False)
        monkeypatch.setattr(profiler, "IS_LINUX", False)
        monkeypatch.setattr(profiler, "IS_MACOS", True)

        def fake_run(args, **kwargs):
            if args[0] == "lsof":
                return _make_run_mock(stdout=LSOF_OUTPUT)
            return _make_run_mock()

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = profiler.snapshot_ports()
        assert result == [3000, 5432, 5433]

    def test_returns_empty_on_lsof_failure(self, monkeypatch):
        """Should return empty list when lsof fails."""
        from aec.lib import profiler

        monkeypatch.setattr(profiler, "IS_WINDOWS", False)
        monkeypatch.setattr(profiler, "IS_LINUX", False)
        monkeypatch.setattr(profiler, "IS_MACOS", True)

        def fake_run(args, **kwargs):
            raise FileNotFoundError("lsof not found")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = profiler.snapshot_ports()
        assert result == []

    def test_parses_netstat_windows(self, monkeypatch):
        """Should parse netstat output on Windows."""
        from aec.lib import profiler

        monkeypatch.setattr(profiler, "IS_WINDOWS", True)
        monkeypatch.setattr(profiler, "IS_LINUX", False)
        monkeypatch.setattr(profiler, "IS_MACOS", False)

        def fake_run(args, **kwargs):
            if args[0] == "netstat":
                return _make_run_mock(stdout=NETSTAT_WINDOWS_OUTPUT)
            return _make_run_mock()

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = profiler.snapshot_ports()
        # Only LISTENING lines: 80, 443 (3000 is ESTABLISHED)
        assert result == [80, 443]


class TestSnapshotProcesses:
    """Test snapshot_processes function."""

    def test_parses_ps_output(self, monkeypatch):
        """Should parse ps aux output to categorize processes."""
        from aec.lib import profiler

        monkeypatch.setattr(profiler, "IS_WINDOWS", False)

        def fake_run(args, **kwargs):
            if args[0] == "ps":
                return _make_run_mock(stdout=PS_AUX_OUTPUT)
            return _make_run_mock()

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = profiler.snapshot_processes()
        assert result["zombies"] == 1
        assert result["stuck_io"] == 1
        assert result["node_processes"] >= 2  # node server.js, node jest, npm
        assert result["test_processes"] >= 1  # jest

    def test_returns_zeros_on_ps_failure(self, monkeypatch):
        """Should return zero counts when ps fails."""
        from aec.lib import profiler

        monkeypatch.setattr(profiler, "IS_WINDOWS", False)

        def fake_run(args, **kwargs):
            raise FileNotFoundError("ps not found")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = profiler.snapshot_processes()
        assert result == {
            "zombies": 0,
            "stuck_io": 0,
            "node_processes": 0,
            "test_processes": 0,
        }


class TestSnapshotDocker:
    """Test snapshot_docker function."""

    def test_parses_docker_ps_output(self, monkeypatch):
        """Should parse docker ps output to get container names."""
        from aec.lib import profiler

        def fake_run(args, **kwargs):
            if args[0] == "docker":
                return _make_run_mock(stdout=DOCKER_PS_OUTPUT)
            return _make_run_mock()

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = profiler.snapshot_docker()
        assert result == ["earnlearn-test-db", "redis-cache"]

    def test_returns_empty_when_docker_unavailable(self, monkeypatch):
        """Should return empty list when docker is not available."""
        from aec.lib import profiler

        def fake_run(args, **kwargs):
            raise FileNotFoundError("docker not found")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = profiler.snapshot_docker()
        assert result == []


class TestTakeSnapshot:
    """Test take_snapshot function."""

    def test_returns_complete_structure(self, monkeypatch):
        """Should return dict with all required keys."""
        from aec.lib import profiler

        monkeypatch.setattr(profiler, "IS_WINDOWS", False)
        monkeypatch.setattr(profiler, "IS_MACOS", True)
        monkeypatch.setattr(profiler, "IS_LINUX", False)

        # Mock all subprocess calls to return empty
        def fake_run(args, **kwargs):
            return _make_run_mock()

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = profiler.take_snapshot()

        assert "ports" in result
        assert "processes" in result
        assert "process_details" in result
        assert "docker_containers" in result
        assert "memory_mb" in result
        assert "timestamp" in result

        assert isinstance(result["ports"], list)
        assert isinstance(result["processes"], dict)
        assert isinstance(result["process_details"], list)
        assert isinstance(result["docker_containers"], list)
        assert isinstance(result["memory_mb"], float)
        assert isinstance(result["timestamp"], str)

        # Timestamp should be UTC ISO format
        assert result["timestamp"].endswith("Z")


class TestDiffSnapshots:
    """Test diff_snapshots function — pure logic, no mocking needed."""

    def test_detects_new_ports(self):
        """Should detect ports that appeared after test run."""
        from aec.lib.profiler import diff_snapshots

        before = {"ports": [3000], "processes": {}, "docker_containers": [], "memory_mb": 0.0, "process_details": []}
        after = {"ports": [3000, 9229, 9230], "processes": {}, "docker_containers": [], "memory_mb": 0.0, "process_details": []}

        result = diff_snapshots(before, after)
        assert result["ports_new"] == [9229, 9230]
        assert result["ports_gone"] == []

    def test_detects_leaked_processes(self):
        """Should detect increase in test process count."""
        from aec.lib.profiler import diff_snapshots

        before = {"ports": [], "processes": {"test_processes": 1}, "docker_containers": [], "memory_mb": 0.0, "process_details": []}
        after = {
            "ports": [],
            "processes": {"test_processes": 4},
            "docker_containers": [],
            "memory_mb": 0.0,
            "process_details": [{"pid": 100, "command": "jest", "elapsed": "00:01:00"}],
        }

        result = diff_snapshots(before, after)
        assert result["processes_leaked"] == 3
        assert len(result["leaked_details"]) == 1

    def test_ignores_process_decrease(self):
        """Should not report decrease in process counts."""
        from aec.lib.profiler import diff_snapshots

        before = {"ports": [], "processes": {"test_processes": 5}, "docker_containers": [], "memory_mb": 0.0, "process_details": []}
        after = {"ports": [], "processes": {"test_processes": 2}, "docker_containers": [], "memory_mb": 0.0, "process_details": []}

        result = diff_snapshots(before, after)
        assert result["processes_leaked"] == 0
        assert result["leaked_details"] == []

    def test_detects_remaining_docker_containers(self):
        """Should detect docker containers still running after test."""
        from aec.lib.profiler import diff_snapshots

        before = {"ports": [], "processes": {}, "docker_containers": [], "memory_mb": 0.0, "process_details": []}
        after = {"ports": [], "processes": {}, "docker_containers": ["test-db"], "memory_mb": 0.0, "process_details": []}

        result = diff_snapshots(before, after)
        assert result["docker_started"] == ["test-db"]
        assert result["docker_remaining"] == ["test-db"]

    def test_identical_snapshots_no_changes(self):
        """Should return no changes for identical snapshots."""
        from aec.lib.profiler import diff_snapshots

        snap = {
            "ports": [3000, 5432],
            "processes": {"test_processes": 2, "node_processes": 5},
            "docker_containers": ["db"],
            "memory_mb": 256.0,
            "process_details": [],
        }

        result = diff_snapshots(snap, snap)
        assert result["ports_new"] == []
        assert result["ports_gone"] == []
        assert result["docker_started"] == []
        assert result["processes_leaked"] == 0
        assert result["leaked_details"] == []
        assert result["memory_delta_mb"] == 0.0


class TestSaveProfile:
    """Test save_profile function."""

    def test_creates_directory_structure(self, temp_dir):
        """Should create profiles/{project}/ directory."""
        from aec.lib.profiler import save_profile

        profile_data = {"ports": [3000], "timestamp": "2026-04-08T02:00:00Z"}
        result = save_profile(temp_dir, "my-project", "2026-04-08T02-00-00Z", profile_data)

        assert result.parent.name == "my-project"
        assert result.parent.parent == temp_dir
        assert result.exists()

    def test_writes_valid_json(self, temp_dir):
        """Should write valid JSON with indent=2."""
        from aec.lib.profiler import save_profile

        profile_data = {"ports": [3000, 5432], "memory_mb": 128.5}
        path = save_profile(temp_dir, "my-project", "2026-04-08T02-00-00Z", profile_data)

        loaded = json.loads(path.read_text())
        assert loaded == profile_data


class TestLoadProfiles:
    """Test load_profiles function."""

    def test_returns_sorted_by_timestamp(self, temp_dir):
        """Should return profiles sorted by filename (timestamp) descending."""
        from aec.lib.profiler import load_profiles, save_profile

        save_profile(temp_dir, "proj", "2026-04-01T00-00-00Z", {"ts": "first"})
        save_profile(temp_dir, "proj", "2026-04-03T00-00-00Z", {"ts": "third"})
        save_profile(temp_dir, "proj", "2026-04-02T00-00-00Z", {"ts": "second"})

        results = load_profiles(temp_dir, "proj")
        assert len(results) == 3
        assert results[0]["ts"] == "third"
        assert results[1]["ts"] == "second"
        assert results[2]["ts"] == "first"

    def test_returns_empty_for_missing_project(self, temp_dir):
        """Should return empty list when project directory doesn't exist."""
        from aec.lib.profiler import load_profiles

        result = load_profiles(temp_dir, "nonexistent-project")
        assert result == []

    def test_respects_limit(self, temp_dir):
        """Should only return up to limit profiles."""
        from aec.lib.profiler import load_profiles, save_profile

        for i in range(5):
            save_profile(temp_dir, "proj", f"2026-04-0{i+1}T00-00-00Z", {"idx": i})

        results = load_profiles(temp_dir, "proj", limit=2)
        assert len(results) == 2
