"""Report generation, retention, and viewer module for AEC quality infrastructure."""

import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


def create_report_dir(base_dir: Path, timestamp: str) -> Path:
    """Create a report directory for the given timestamp.

    Args:
        base_dir: Parent directory for all reports.
        timestamp: ISO timestamp used as directory name.

    Returns:
        Path to the created directory.
    """
    report_dir = base_dir / timestamp
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def write_suite_output(report_dir: Path, project_name: str, output: str) -> Path:
    """Write raw test output to a file in the report directory.

    Args:
        report_dir: Directory to write the output file.
        project_name: Name of the project (used in filename).
        output: Raw test output string.

    Returns:
        Path to the written file.
    """
    file_path = report_dir / f"{project_name}_test_output.txt"
    file_path.write_text(output)
    return file_path


def generate_summary(
    report_dir: Path,
    results: List[Dict],
    port_observations: List[Dict],
    process_observations: List[Dict],
    execution_order: List[str],
    seed: int,
    retention_mode: str,
    report_count: int,
) -> Path:
    """Write a summary.txt in the report directory.

    Args:
        report_dir: Directory to write summary.txt.
        results: List of result dicts with project, suite, status, etc.
        port_observations: List of port observation dicts.
        process_observations: List of process observation dicts.
        execution_order: List of project names in execution order.
        seed: Random seed used for ordering.
        retention_mode: "manual" or "auto".
        report_count: Number of report days that exist.

    Returns:
        Path to the written summary.txt.
    """
    lines: List[str] = []

    # Header with timestamp from directory name
    timestamp_str = report_dir.name
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        display_time = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        display_time = timestamp_str

    lines.append(f"AEC Test Report — {display_time}")
    order_str = ", ".join(execution_order)
    lines.append(f"Execution order: {order_str} (seed: {seed})")

    if retention_mode == "manual":
        lines.append(
            f"Note: {report_count} days of reports exist in "
            "~/.agents-environment-config/tests/"
        )

    lines.append("")
    lines.append("──────────────────────────────────────────")

    # Group results by project
    projects_seen: List[str] = []
    results_by_project: Dict[str, List[Dict]] = {}
    for r in results:
        proj = r["project"]
        if proj not in results_by_project:
            projects_seen.append(proj)
            results_by_project[proj] = []
        results_by_project[proj].append(r)

    for proj in projects_seen:
        lines.append("")
        lines.append(proj)
        for r in results_by_project[proj]:
            suite = r["suite"]
            status = r["status"]
            duration = r.get("duration_seconds")
            skip_reason = r.get("skip_reason")

            if status == "passed":
                symbol = "✓"
                duration_str = f"{duration:.1f}s" if duration is not None else ""
                lines.append(f"  {symbol} {suite:<14}{duration_str}   passed")
            elif status == "skipped":
                symbol = "⊘"
                reason_str = f" ({skip_reason})" if skip_reason else ""
                lines.append(f"  {symbol} {suite:<14}skipped{reason_str}")
            elif status == "failed":
                symbol = "✗"
                duration_str = f"{duration:.1f}s" if duration is not None else ""
                exit_code = r.get("exit_code", 1)
                lines.append(
                    f"  {symbol} {suite:<14}{duration_str}   "
                    f"FAILED (exit code {exit_code})"
                )
                lines.append(f"    → see {proj}_test_output.txt")

    lines.append("")
    lines.append("──────────────────────────────────────────")

    if port_observations:
        lines.append("")
        lines.append("Port observations:")
        for obs in port_observations:
            project = obs.get("project", "unknown")
            ports = obs.get("ports", [])
            ports_str = ", ".join(str(p) for p in ports)
            lines.append(
                f"  {project}: ports {ports_str} appeared during tests "
                "— not registered in AEC"
            )

    if process_observations:
        lines.append("")
        lines.append("Process observations:")
        for obs in process_observations:
            label = obs.get("label", "unknown")
            count = obs.get("count", 0)
            pids = obs.get("pids", [])
            pids_str = ", ".join(str(p) for p in pids)
            lines.append(
                f"  {label}: {count} node processes leaked "
                f"(PIDs: {pids_str})"
            )

    lines.append("")

    summary_path = report_dir / "summary.txt"
    summary_path.write_text("\n".join(lines))
    return summary_path


def count_report_days(base_dir: Path) -> int:
    """Count the number of date-stamped directories in the tests/ dir.

    Args:
        base_dir: Directory containing report subdirectories.

    Returns:
        Number of directories found. 0 if base_dir doesn't exist.
    """
    if not base_dir.exists():
        return 0
    return sum(1 for p in base_dir.iterdir() if p.is_dir())


def prune_old_reports(base_dir: Path, max_days: int) -> int:
    """Delete report directories older than max_days.

    Compares directory name (ISO timestamp) against current time.

    Args:
        base_dir: Directory containing report subdirectories.
        max_days: Maximum age in days to keep.

    Returns:
        Count of directories deleted.
    """
    if not base_dir.exists():
        return 0

    now = datetime.now(timezone.utc)
    deleted = 0

    for entry in list(base_dir.iterdir()):
        if not entry.is_dir():
            continue
        try:
            dir_time = datetime.fromisoformat(
                entry.name.replace("Z", "+00:00")
            )
            age_days = (now - dir_time).total_seconds() / 86400
            if age_days > max_days:
                shutil.rmtree(entry)
                deleted += 1
        except (ValueError, AttributeError):
            continue

    return deleted


def prune_old_profiles(profiles_dir: Path, max_days: int) -> int:
    """Delete profile JSON files older than max_days across all project subdirectories.

    Args:
        profiles_dir: Directory containing project subdirectories with profile JSONs.
        max_days: Maximum age in days to keep.

    Returns:
        Count of files deleted.
    """
    if not profiles_dir.exists():
        return 0

    now = datetime.now(timezone.utc)
    deleted = 0

    for project_dir in profiles_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for profile_file in list(project_dir.iterdir()):
            if not profile_file.is_file() or profile_file.suffix != ".json":
                continue
            # Use file modification time
            mtime = datetime.fromtimestamp(
                profile_file.stat().st_mtime, tz=timezone.utc
            )
            age_days = (now - mtime).total_seconds() / 86400
            if age_days > max_days:
                profile_file.unlink()
                deleted += 1

    return deleted


def open_report(report_path: Path, viewer_key: str) -> bool:
    """Open a report file using the configured viewer.

    Args:
        report_path: Path to the report file to open.
        viewer_key: Viewer key from preferences (e.g. "vscode", "nano").

    Returns:
        True if the report was opened, False if no viewer available.
    """
    try:
        from aec.lib.viewers import get_viewer_command, format_viewer_command

        command = get_viewer_command(viewer_key)
        if command is not None:
            formatted = format_viewer_command(command, str(report_path))
            subprocess.Popen(
                formatted, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return True
    except ImportError:
        pass

    # Fallback: platform-specific opener
    system = sys.platform
    if system == "darwin":
        subprocess.Popen(
            ["open", str(report_path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    elif system.startswith("linux"):
        try:
            subprocess.Popen(
                ["xdg-open", str(report_path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return True
        except FileNotFoundError:
            return False

    return False
