"""System state profiling for test runs.

Takes system state snapshots before/after test suite execution.
Read-only — never kills processes or modifies system state.
"""

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from aec.lib.config import IS_LINUX, IS_MACOS, IS_WINDOWS


def _run_cmd(args: list[str], timeout: int = 10) -> str:
    """Run a subprocess and return stdout, or empty string on any failure."""
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""


def snapshot_ports() -> list[int]:
    """Get sorted list of ports currently being listened on."""
    ports: set[int] = set()

    if IS_WINDOWS:
        output = _run_cmd(["netstat", "-ano"])
        for line in output.splitlines():
            if "LISTENING" in line:
                parts = line.split()
                if len(parts) >= 2:
                    # Local address is like 0.0.0.0:8080 or [::]:8080
                    addr = parts[1]
                    port_str = addr.rsplit(":", 1)[-1]
                    try:
                        ports.add(int(port_str))
                    except ValueError:
                        continue
    else:
        # macOS / Linux: try lsof first
        output = _run_cmd(["lsof", "-i", "-P", "-n", "-sTCP:LISTEN"])
        if output:
            for line in output.splitlines()[1:]:  # skip header
                parts = line.split()
                if len(parts) >= 9:
                    # Name column (index 8) looks like *:8080 or 127.0.0.1:3000
                    name = parts[8]
                    port_str = name.rsplit(":", 1)[-1]
                    try:
                        ports.add(int(port_str))
                    except ValueError:
                        continue
        elif IS_LINUX:
            # Fallback: ss on Linux
            output = _run_cmd(["ss", "-tlnp"])
            for line in output.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 4:
                    addr = parts[3]
                    port_str = addr.rsplit(":", 1)[-1]
                    try:
                        ports.add(int(port_str))
                    except ValueError:
                        continue

    return sorted(ports)


def snapshot_processes() -> dict:
    """Count process categories. Returns counts, not PIDs."""
    result = {
        "zombies": 0,
        "stuck_io": 0,
        "node_processes": 0,
        "test_processes": 0,
    }

    if IS_WINDOWS:
        output = _run_cmd(["tasklist", "/FO", "CSV", "/NH"])
        for line in output.splitlines():
            lower = line.lower()
            if "node.exe" in lower or "npm.exe" in lower:
                result["node_processes"] += 1
            if any(
                t in lower
                for t in ["jest", "vitest", "pytest", "playwright"]
            ):
                result["test_processes"] += 1
        return result

    # macOS / Linux
    output = _run_cmd(["ps", "aux"])
    if not output:
        return result

    for line in output.splitlines()[1:]:  # skip header
        parts = line.split(None, 10)  # split into max 11 fields
        if len(parts) < 8:
            continue
        stat = parts[7]  # STAT column in ps aux
        command = parts[10] if len(parts) > 10 else ""
        command_lower = command.lower()

        if stat.startswith("Z"):
            result["zombies"] += 1
        if stat.startswith("D"):
            result["stuck_io"] += 1

        # Check full command for node/npm
        if re.search(r"\bnode\b|\bnpm\b", command_lower):
            result["node_processes"] += 1

        # Check for test runners
        if re.search(r"\bjest\b|\bvitest\b|\bpytest\b|\bplaywright\b", command_lower):
            result["test_processes"] += 1

    return result


def snapshot_process_details() -> list[dict]:
    """Get details of test-related processes (pid, command, elapsed)."""
    details: list[dict] = []

    if IS_WINDOWS:
        output = _run_cmd([
            "powershell", "-Command",
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.CommandLine -match 'jest|vitest|pytest|playwright' } | "
            "Select-Object ProcessId, CommandLine | "
            "Format-List"
        ])
        current: dict = {}
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("ProcessId"):
                pid_str = line.split(":", 1)[1].strip()
                try:
                    current["pid"] = int(pid_str)
                except ValueError:
                    continue
            elif line.startswith("CommandLine"):
                current["command"] = line.split(":", 1)[1].strip()
                current["elapsed"] = "unknown"
                details.append(current)
                current = {}
        return details

    # macOS / Linux
    pgrep_output = _run_cmd(["pgrep", "-f", "jest|vitest|pytest|playwright", "-l"])
    if not pgrep_output:
        return details

    for line in pgrep_output.splitlines():
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        command = parts[1]

        # Get elapsed time for this PID
        elapsed_output = _run_cmd(["ps", "-p", str(pid), "-o", "etime="])
        elapsed = elapsed_output.strip() if elapsed_output else "unknown"

        details.append({"pid": pid, "command": command, "elapsed": elapsed})

    return details


def snapshot_docker() -> list[str]:
    """Get list of running Docker container names."""
    output = _run_cmd(["docker", "ps", "--format", "{{.Names}}"])
    if not output:
        return []
    return [name.strip() for name in output.splitlines() if name.strip()]


def snapshot_memory() -> float:
    """Get current memory usage of children in MB."""
    if IS_WINDOWS:
        output = _run_cmd([
            "wmic", "process", "where",
            "ParentProcessId=" + str(os.getpid()),
            "get", "WorkingSetSize",
        ])
        total = 0
        for line in output.splitlines():
            line = line.strip()
            try:
                total += int(line)
            except ValueError:
                continue
        return total / (1024 * 1024) if total else 0.0

    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        if IS_MACOS:
            return usage.ru_maxrss / (1024 * 1024)  # bytes on macOS
        else:
            return usage.ru_maxrss / 1024  # KB on Linux
    except (ImportError, OSError):
        return 0.0


def take_snapshot() -> dict:
    """Take a complete system state snapshot."""
    return {
        "ports": snapshot_ports(),
        "processes": snapshot_processes(),
        "process_details": snapshot_process_details(),
        "docker_containers": snapshot_docker(),
        "memory_mb": snapshot_memory(),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def diff_snapshots(before: dict, after: dict) -> dict:
    """Compare two snapshots. Only reports increases for process counts."""
    before_ports = set(before.get("ports", []))
    after_ports = set(after.get("ports", []))

    before_docker = set(before.get("docker_containers", []))
    after_docker = set(after.get("docker_containers", []))

    before_procs = before.get("processes", {})
    after_procs = after.get("processes", {})

    # Process leak: only count increase in test_processes
    test_before = before_procs.get("test_processes", 0)
    test_after = after_procs.get("test_processes", 0)
    processes_leaked = max(0, test_after - test_before)

    return {
        "ports_new": sorted(after_ports - before_ports),
        "ports_gone": sorted(before_ports - after_ports),
        "docker_started": sorted(after_docker - before_docker),
        "docker_remaining": sorted(after_docker),
        "processes_leaked": processes_leaked,
        "leaked_details": after.get("process_details", []) if processes_leaked > 0 else [],
        "memory_delta_mb": round(
            after.get("memory_mb", 0.0) - before.get("memory_mb", 0.0), 2
        ),
    }


def save_profile(
    profiles_dir: Path, project_name: str, timestamp: str, profile_data: dict
) -> Path:
    """Save profile JSON to profiles/{project}/{timestamp}.json."""
    project_dir = profiles_dir / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    file_path = project_dir / f"{timestamp}.json"
    file_path.write_text(json.dumps(profile_data, indent=2))
    return file_path


def load_profiles(
    profiles_dir: Path, project_name: str, limit: int = 10
) -> list[dict]:
    """Load recent profiles for a project, sorted by timestamp descending."""
    project_dir = profiles_dir / project_name
    if not project_dir.is_dir():
        return []

    files = sorted(project_dir.glob("*.json"), reverse=True)
    results: list[dict] = []
    for f in files[:limit]:
        try:
            data = json.loads(f.read_text())
            results.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return results
