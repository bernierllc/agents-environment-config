"""Ports commands: aec ports {list|check|register|unregister|validate}"""

import json
from pathlib import Path

from ..lib.config import AEC_PORTS_REGISTRY
from ..lib.console import Console
from ..lib.ports import (
    load_registry,
    save_registry,
    register_port,
    unregister_project_ports,
    check_conflicts,
    validate_registry,
    list_ports_by_project,
)


def run_ports_list() -> None:
    """Show all registered ports grouped by project, sorted by port number."""
    registry = load_registry(AEC_PORTS_REGISTRY)
    grouped = list_ports_by_project(registry)

    if not grouped:
        Console.info("No ports registered.")
        return

    for project, entries in sorted(grouped.items()):
        Console.subheader(project)
        for entry in entries:
            protocol = f" ({entry['protocol']})" if entry.get("protocol") else ""
            desc = f" - {entry['description']}" if entry.get("description") else ""
            Console.print(f"    {entry['port']:>5}  {entry['key']}{protocol}{desc}")

    total = sum(len(entries) for entries in grouped.values())
    Console.info(f"{total} port(s) registered across {len(grouped)} project(s).")


def run_ports_check(path: str) -> None:
    """Check a project's .aec.json ports against the registry without registering."""
    project_path = str(Path(path).resolve())
    aec_json_path = Path(project_path) / ".aec.json"

    if not aec_json_path.exists():
        Console.error(f"No .aec.json found at {project_path}")
        return

    try:
        with open(aec_json_path) as f:
            aec_config = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        Console.error(f"Failed to read .aec.json: {exc}")
        return

    ports = aec_config.get("ports", {})
    if not ports:
        Console.info("No ports defined in .aec.json")
        return

    registry = load_registry(AEC_PORTS_REGISTRY)
    conflicts = check_conflicts(registry, ports, project_path)

    if conflicts:
        Console.warning(f"Found {len(conflicts)} conflict(s):")
        for c in conflicts:
            Console.warning(
                f"  Port {c['port']} ({c['key']}) already registered to "
                f"{c['existing_project']} (since {c['registered_at']})"
            )
    else:
        Console.success(f"No conflicts found for {len(ports)} port(s).")


def run_ports_register(path: str) -> None:
    """Register ports from a project's .aec.json. Skip conflicts with warnings."""
    project_path = str(Path(path).resolve())
    aec_json_path = Path(project_path) / ".aec.json"

    if not aec_json_path.exists():
        Console.error(f"No .aec.json found at {project_path}")
        return

    try:
        with open(aec_json_path) as f:
            aec_config = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        Console.error(f"Failed to read .aec.json: {exc}")
        return

    project_name = aec_config.get("project", Path(project_path).name)
    ports = aec_config.get("ports", {})
    if not ports:
        Console.info("No ports defined in .aec.json")
        return

    registry = load_registry(AEC_PORTS_REGISTRY)
    registered_count = 0

    for key_name, spec in ports.items():
        port = spec.get("port")
        if port is None:
            continue
        result = register_port(
            registry,
            port=port,
            project=project_name,
            project_path=project_path,
            key=key_name,
            protocol=spec.get("protocol", ""),
            description=spec.get("description", ""),
        )
        if result == "registered":
            Console.success(f"Registered port {port} ({key_name})")
            registered_count += 1
        else:
            existing = registry["ports"][str(port)]
            Console.warning(
                f"Port {port} ({key_name}) already registered to "
                f"{existing['project']}"
            )

    save_registry(registry, AEC_PORTS_REGISTRY)
    Console.info(f"Registered {registered_count} port(s) for {project_name}.")


def run_ports_unregister(path: str) -> None:
    """Remove all port registrations for a project."""
    project_path = str(Path(path).resolve())
    registry = load_registry(AEC_PORTS_REGISTRY)
    freed = unregister_project_ports(registry, project_path)

    if freed:
        save_registry(registry, AEC_PORTS_REGISTRY)
        Console.success(f"Freed {len(freed)} port(s): {', '.join(str(p) for p in freed)}")
    else:
        Console.info("No ports registered for this project.")


def run_ports_validate() -> None:
    """Scan registry for stale entries (dead paths). Report but don't remove."""
    registry = load_registry(AEC_PORTS_REGISTRY)
    stale = validate_registry(registry)

    if not stale:
        Console.success("All registered paths are valid.")
        return

    Console.warning(f"Found {len(stale)} stale entry/entries:")
    for entry in stale:
        Console.warning(
            f"  Port {entry['port']} ({entry['key']}) -> "
            f"{entry['project_path']} (project: {entry['project']})"
        )
    Console.info("Run 'aec ports unregister <path>' to clean up stale entries.")
