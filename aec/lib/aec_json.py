"""Library for reading, writing, and managing .aec.json project config files."""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

AEC_JSON_FILENAME = ".aec.json"
AEC_JSON_SCHEMA_VERSION = "1.0.0"


def create_skeleton(project_name: str, description: str = "") -> dict:
    """Return a new .aec.json dict with all required sections."""
    return {
        "$schema": "https://aec.bernier.dev/schema/aec.json",
        "version": AEC_JSON_SCHEMA_VERSION,
        "project": {"name": project_name, "description": description},
        "ports": {},
        "test": {"suites": {}, "prerequisites": [], "scheduled": []},
        "installed": {"skills": {}, "rules": {}, "agents": {}},
    }


def load_aec_json(project_dir: Path) -> Optional[dict]:
    """Load .aec.json from project dir.

    Returns None if the file does not exist.
    Returns a default skeleton if the file contains corrupt JSON (logs warning).
    """
    filepath = project_dir / AEC_JSON_FILENAME
    if not filepath.exists():
        return None

    text = filepath.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Corrupt .aec.json in %s: %s — returning default skeleton", project_dir, exc)
        return create_skeleton(project_name=project_dir.name)


def save_aec_json(project_dir: Path, data: dict) -> None:
    """Write .aec.json with pretty-printed JSON. Creates the file if it doesn't exist."""
    filepath = project_dir / AEC_JSON_FILENAME
    filepath.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def aec_json_exists(project_dir: Path) -> bool:
    """Check if .aec.json exists in project dir."""
    return (project_dir / AEC_JSON_FILENAME).exists()


def update_ports_section(data: dict, ports: dict) -> dict:
    """Update the ports section, merging new ports with existing ones.

    Does not remove existing keys. Returns updated dict.
    """
    data.setdefault("ports", {}).update(ports)
    return data


def update_test_section(
    data: dict,
    suites: Optional[dict] = None,
    prerequisites: Optional[list] = None,
    scheduled: Optional[list] = None,
) -> dict:
    """Update the test section. Only updates provided fields. Returns updated dict."""
    test = data.setdefault("test", {"suites": {}, "prerequisites": [], "scheduled": []})
    if suites is not None:
        test["suites"] = suites
    if prerequisites is not None:
        test["prerequisites"] = prerequisites
    if scheduled is not None:
        test["scheduled"] = scheduled
    return data


def update_suite_prerequisites(data: dict, suite_name: str, prerequisites: list) -> dict:
    """Update prerequisites for a specific test suite.

    Args:
        data: The .aec.json data dict.
        suite_name: Name of the suite to update.
        prerequisites: List of prerequisite names.

    Returns:
        Updated data dict.
    """
    test = data.setdefault("test", {"suites": {}, "prerequisites": [], "scheduled": []})
    suite = test["suites"].setdefault(suite_name, {})
    suite["prerequisites"] = prerequisites
    return data


def get_suite_prerequisites(data: dict, suite_name: str) -> list:
    """Get prerequisites for a specific test suite.

    Args:
        data: The .aec.json data dict.
        suite_name: Name of the suite.

    Returns:
        List of prerequisite names, or empty list if none.
    """
    test = data.get("test", {})
    suite = test.get("suites", {}).get(suite_name, {})
    return suite.get("prerequisites", [])


def update_installed_section(data: dict, installed: dict) -> dict:
    """Replace the installed section wholesale. Returns updated dict."""
    data["installed"] = installed
    return data


def manage_aec_json_gitignore(project_dir: Path, should_ignore: bool) -> str:
    """Add or remove .aec.json from the project's .gitignore.

    Returns one of: "added", "removed", "already_ignored",
    "already_tracked", or "no_gitignore".
    """
    gitignore_path = project_dir / ".gitignore"

    if not gitignore_path.exists():
        if should_ignore:
            gitignore_path.write_text(AEC_JSON_FILENAME + "\n", encoding="utf-8")
            return "added"
        return "no_gitignore"

    text = gitignore_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Check if .aec.json is already in .gitignore (exact match or with trailing comment)
    ignored = False
    for line in lines:
        stripped = line.split("#")[0].strip()
        if stripped == AEC_JSON_FILENAME:
            ignored = True
            break

    if should_ignore:
        if ignored:
            return "already_ignored"
        # Append the entry
        if text and not text.endswith("\n"):
            text += "\n"
        text += AEC_JSON_FILENAME + "\n"
        gitignore_path.write_text(text, encoding="utf-8")
        return "added"
    else:
        if not ignored:
            return "already_tracked"
        # Remove lines that match .aec.json
        new_lines = []
        for line in lines:
            stripped = line.split("#")[0].strip()
            if stripped != AEC_JSON_FILENAME:
                new_lines.append(line)
        gitignore_path.write_text("\n".join(new_lines) + "\n" if new_lines else "", encoding="utf-8")
        return "removed"
