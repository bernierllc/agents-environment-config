"""Port registry CRUD operations for project port management."""

import json
from datetime import datetime, timezone
from pathlib import Path


def _default_registry() -> dict:
    """Return the default empty registry structure."""
    return {"version": "1.0.0", "ports": {}}


def load_registry(registry_path: Path) -> dict:
    """Load ports-registry.json, return default structure if missing/corrupt.

    Args:
        registry_path: Path to the ports-registry.json file.

    Returns:
        Registry dict with 'version' and 'ports' keys.
    """
    if not registry_path.exists():
        return _default_registry()

    try:
        data = json.loads(registry_path.read_text())
    except (json.JSONDecodeError, OSError):
        return _default_registry()

    # Validate structure
    if not isinstance(data, dict) or "version" not in data or "ports" not in data:
        return _default_registry()

    return data


def save_registry(registry: dict, registry_path: Path) -> None:
    """Write registry to disk, creating parent dirs if needed.

    Args:
        registry: The registry dict to persist.
        registry_path: Path to write the file to.
    """
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2) + "\n")


def register_port(
    registry: dict,
    port: int,
    project: str,
    project_path: str,
    key: str,
    protocol: str = "",
    description: str = "",
) -> str:
    """Register a port in the registry.

    First-come-first-served: does NOT overwrite existing registrations.

    Args:
        registry: The registry dict (mutated in place).
        port: Port number to register.
        project: Human-readable project name.
        project_path: Absolute path to the project directory.
        key: Key name from .aec.json (e.g. 'dev_server', 'api').
        protocol: Optional protocol (e.g. 'http', 'https').
        description: Optional description of what uses this port.

    Returns:
        "registered" if the port was newly registered,
        "conflict" if the port is already taken.
    """
    port_key = str(port)

    if port_key in registry["ports"]:
        return "conflict"

    registry["ports"][port_key] = {
        "project": project,
        "project_path": project_path,
        "key": key,
        "protocol": protocol,
        "description": description,
        "registered_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return "registered"


def unregister_project_ports(registry: dict, project_path: str) -> list[int]:
    """Remove all ports for a project path.

    Args:
        registry: The registry dict (mutated in place).
        project_path: Path of the project whose ports to remove.

    Returns:
        List of freed port numbers.
    """
    freed: list[int] = []
    to_remove = [
        port_key
        for port_key, entry in registry["ports"].items()
        if entry["project_path"] == project_path
    ]
    for port_key in to_remove:
        del registry["ports"][port_key]
        freed.append(int(port_key))

    return sorted(freed)


def check_conflicts(
    registry: dict, ports: dict, project_path: str
) -> list[dict]:
    """Check a dict of port assignments against the registry.

    Args:
        registry: The current registry dict.
        ports: Port assignments from .aec.json format:
               {"key_name": {"port": 3000, ...}, ...}
        project_path: Path of the project being checked (its own
                      registrations are not considered conflicts).

    Returns:
        List of conflict dicts with keys: port, key, existing_project,
        registered_at.
    """
    conflicts: list[dict] = []
    for key_name, spec in ports.items():
        port = spec.get("port")
        if port is None:
            continue
        port_key = str(port)
        if port_key in registry["ports"]:
            existing = registry["ports"][port_key]
            if existing["project_path"] != project_path:
                conflicts.append({
                    "port": port,
                    "key": key_name,
                    "existing_project": existing["project"],
                    "registered_at": existing["registered_at"],
                })
    return conflicts


def validate_registry(registry: dict) -> list[dict]:
    """Check all entries for stale project paths.

    Args:
        registry: The registry dict to validate.

    Returns:
        List of entry dicts where project_path no longer exists on disk.
    """
    stale: list[dict] = []
    for port_key, entry in registry["ports"].items():
        if not Path(entry["project_path"]).exists():
            stale.append({"port": int(port_key), **entry})
    return stale


def list_ports_by_project(registry: dict) -> dict[str, list[dict]]:
    """Group port entries by project name for display.

    Args:
        registry: The registry dict.

    Returns:
        Dict mapping project name to list of port entry dicts
        (each including a 'port' key with the integer port number).
    """
    grouped: dict[str, list[dict]] = {}
    for port_key, entry in registry["ports"].items():
        project = entry["project"]
        if project not in grouped:
            grouped[project] = []
        grouped[project].append({"port": int(port_key), **entry})

    # Sort each project's ports by port number
    for project in grouped:
        grouped[project].sort(key=lambda e: e["port"])

    return grouped
