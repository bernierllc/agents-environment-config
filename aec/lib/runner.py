"""Test runner — executes test suites for tracked projects.

Stub module: will be fully implemented by a parallel unit.
"""

import subprocess
from pathlib import Path

from .console import Console


def run_single_project(project_dir: Path, run_all: bool = False) -> int:
    """Run test suites for a single project.

    Returns exit code (0 = all passed).
    """
    from .aec_json import load_aec_json

    data = load_aec_json(project_dir)
    if data is None:
        Console.warning(f"No .aec.json found in {project_dir}")
        return 1

    suites = (data.get("test") or {}).get("suites") or {}
    if not suites:
        Console.info("No test suites configured.")
        return 0

    exit_code = 0
    for name, suite in suites.items():
        cmd = suite.get("command")
        if not cmd:
            continue
        Console.subheader(f"Running: {name}")
        Console.print(f"  $ {cmd}")
        result = subprocess.run(
            cmd, shell=True, cwd=str(project_dir),
        )
        if result.returncode != 0:
            Console.error(f"Suite '{name}' failed (exit {result.returncode})")
            exit_code = 1
        else:
            Console.success(f"Suite '{name}' passed")

    return exit_code


def run_all_projects(global_mode: bool = True) -> int:
    """Run test suites across all tracked projects.

    Returns exit code (0 = all passed).
    """
    from .tracking import list_repos

    repos = list_repos()
    if not repos:
        Console.info("No tracked projects found.")
        return 0

    exit_code = 0
    for repo in repos:
        repo_path = Path(repo.path)
        if not repo_path.is_dir():
            continue
        Console.subheader(f"Project: {repo_path.name}")
        rc = run_single_project(repo_path, run_all=True)
        if rc != 0:
            exit_code = 1

    return exit_code
