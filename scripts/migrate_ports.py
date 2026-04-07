#!/usr/bin/env python3
"""One-time migration: convert ~/projects/ports.json to AEC format.

This creates:
1. .aec.json files for select projects (earnlearn, mbernier.com)
2. ports-registry.json with all projects' ports
3. Backup of original ports.json

Usage:
    python scripts/migrate_ports.py [--dry-run] [--projects-dir ~/projects]
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Projects that should get .aec.json files placed in their directories.
# These are preferred because they have rich port configs and test databases.
PREFERRED_AEC_JSON_PROJECTS = ["earnlearn", "barevents", "mbernier.com"]

AEC_HOME = Path.home() / ".agents-environment-config"
PORTS_REGISTRY_PATH = AEC_HOME / "ports-registry.json"
SCHEMA_URL = "https://aec.bernier.dev/schema/aec.json"


def load_ports_json(ports_path: Path) -> dict[str, Any]:
    """Load and validate the source ports.json file."""
    if not ports_path.exists():
        print(f"ERROR: {ports_path} not found")
        sys.exit(1)

    with open(ports_path, "r") as f:
        data = json.load(f)

    if "projects" not in data:
        print("ERROR: ports.json missing 'projects' key")
        sys.exit(1)

    return data


def backup_ports_json(ports_path: Path, dry_run: bool) -> None:
    """Create a backup of the original ports.json."""
    backup_path = ports_path.with_suffix(".json.bak")
    if backup_path.exists():
        print(f"  Backup already exists: {backup_path}")
        return
    if dry_run:
        print(f"  [dry-run] Would create backup: {backup_path}")
        return
    shutil.copy2(ports_path, backup_path)
    print(f"  Created backup: {backup_path}")


def convert_port_entry(old_entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a port entry from the old format to the new .aec.json format.

    Drops: environment, required, notes, shared_with
    Keeps: port, protocol, description
    """
    new_entry: dict[str, Any] = {"port": old_entry["port"]}
    if "protocol" in old_entry:
        new_entry["protocol"] = old_entry["protocol"]
    if "description" in old_entry:
        new_entry["description"] = old_entry["description"]
    return new_entry


def build_aec_json(project_name: str, project_data: dict[str, Any]) -> dict[str, Any]:
    """Build a .aec.json structure for a project."""
    ports = {}
    for key, port_data in project_data.get("ports", {}).items():
        ports[key] = convert_port_entry(port_data)

    return {
        "$schema": SCHEMA_URL,
        "version": "1.0.0",
        "project": {
            "name": project_name,
            "description": project_data.get("description", ""),
        },
        "ports": ports,
        "test": {"suites": {}, "prerequisites": [], "scheduled": []},
        "installed": {"skills": {}, "rules": {}, "agents": {}},
    }


def write_aec_json_files(
    projects: dict[str, Any], projects_dir: Path, dry_run: bool
) -> list[str]:
    """Write .aec.json files for preferred projects that exist on disk.

    Returns list of project names that got .aec.json files.
    """
    created = []
    for name in PREFERRED_AEC_JSON_PROJECTS:
        if name not in projects:
            print(f"  Skipping {name}: not in ports.json")
            continue

        project_dir = projects_dir / name
        if not project_dir.is_dir():
            print(f"  Skipping {name}: directory {project_dir} does not exist")
            continue

        aec_json_path = project_dir / ".aec.json"
        aec_data = build_aec_json(name, projects[name])

        if dry_run:
            print(f"  [dry-run] Would write: {aec_json_path}")
        else:
            with open(aec_json_path, "w") as f:
                json.dump(aec_data, f, indent=2)
                f.write("\n")
            print(f"  Created: {aec_json_path}")

        created.append(name)

    return created


def build_ports_registry(
    projects: dict[str, Any], projects_dir: Path
) -> tuple[dict[str, Any], list[str]]:
    """Build the central ports-registry.json from all projects.

    Returns (registry_data, conflict_messages).
    Uses first-come-first-served: the first project to claim a port wins.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    registry: dict[str, Any] = {}
    conflicts: list[str] = []

    for project_name, project_data in projects.items():
        project_path = str(projects_dir / project_name)
        for key, port_data in project_data.get("ports", {}).items():
            port_str = str(port_data["port"])

            if port_str in registry:
                existing = registry[port_str]
                msg = (
                    f"  \u26a0 Port {port_str} already registered to "
                    f"{existing['project']} ({existing['key']}), "
                    f"skipping for {project_name} ({key})"
                )
                conflicts.append(msg)
                continue

            registry[port_str] = {
                "project": project_name,
                "project_path": project_path,
                "key": key,
                "protocol": port_data.get("protocol", "http"),
                "description": port_data.get("description", ""),
                "registered_at": now,
            }

    return {"version": "1.0.0", "ports": registry}, conflicts


def write_ports_registry(
    registry_data: dict[str, Any], dry_run: bool
) -> None:
    """Write the central ports-registry.json."""
    if dry_run:
        print(f"  [dry-run] Would write: {PORTS_REGISTRY_PATH}")
        return

    PORTS_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PORTS_REGISTRY_PATH, "w") as f:
        json.dump(registry_data, f, indent=2)
        f.write("\n")
    print(f"  Created: {PORTS_REGISTRY_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate ~/projects/ports.json to AEC format"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing files",
    )
    parser.add_argument(
        "--projects-dir",
        type=Path,
        default=Path.home() / "projects",
        help="Base directory for projects (default: ~/projects)",
    )
    args = parser.parse_args()

    projects_dir: Path = args.projects_dir.expanduser()
    ports_path = projects_dir / "ports.json"

    print("=== AEC Port Migration ===\n")

    # Step 1: Load source data
    print("1. Loading ports.json...")
    data = load_ports_json(ports_path)
    projects = data["projects"]
    total_projects = len(projects)
    total_ports = sum(
        len(p.get("ports", {})) for p in projects.values()
    )
    print(f"   Found {total_projects} projects with {total_ports} port assignments\n")

    # Step 2: Backup
    print("2. Creating backup...")
    backup_ports_json(ports_path, args.dry_run)
    print()

    # Step 3: Create .aec.json files for select projects
    print("3. Creating .aec.json files for preferred projects...")
    aec_projects = write_aec_json_files(projects, projects_dir, args.dry_run)
    print()

    # Step 4: Build and write central registry
    print("4. Building central port registry...")
    registry_data, conflicts = build_ports_registry(projects, projects_dir)
    registered_count = len(registry_data["ports"])
    write_ports_registry(registry_data, args.dry_run)
    print()

    # Step 5: Report conflicts
    if conflicts:
        print("5. Port conflicts (first-come-first-served):")
        for msg in conflicts:
            print(msg)
        print()

    # Summary
    print("=== Summary ===")
    print(f"  Projects processed: {total_projects}")
    print(f"  Total port assignments in source: {total_ports}")
    print(f"  Ports registered (unique): {registered_count}")
    print(f"  Conflicts found: {len(conflicts)}")
    print(f"  .aec.json files created: {len(aec_projects)}")
    if aec_projects:
        for name in aec_projects:
            print(f"    - {projects_dir / name / '.aec.json'}")


if __name__ == "__main__":
    main()
