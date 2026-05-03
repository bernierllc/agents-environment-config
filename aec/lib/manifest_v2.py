"""V2 manifest: global and per-repo installs for skills, rules, and agents."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .skills_manifest import build_skill_manifest_item

MANIFEST_VERSION = 2
ITEM_TYPES = ("skills", "rules", "agents", "mcps")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_scope() -> dict:
    return {"skills": {}, "rules": {}, "agents": {}, "mcps": {}}


def _empty_manifest() -> dict:
    return {
        "manifestVersion": MANIFEST_VERSION,
        "installedAt": _now_iso(),
        "updatedAt": _now_iso(),
        "lastUpdateCheck": None,
        "global": _empty_scope(),
        "repos": {},
    }


def _backfill_installed_as(manifest: dict) -> None:
    """Backfill installedAs='explicit' for skill records that predate this field."""
    def _backfill_scope(scope_dict: dict) -> None:
        for rec in scope_dict.get("skills", {}).values():
            if isinstance(rec, dict) and "installedAs" not in rec:
                rec["installedAs"] = "explicit"

    _backfill_scope(manifest.get("global", {}))
    for scope_dict in manifest.get("repos", {}).values():
        _backfill_scope(scope_dict)


def load_manifest(path: Path) -> dict:
    """Load a v2 manifest from disk, or return an empty v2 structure."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("manifestVersion") == MANIFEST_VERSION:
                data.setdefault("global", _empty_scope())
                data.setdefault("repos", {})
                data.setdefault("lastUpdateCheck", None)
                for key in ITEM_TYPES:
                    data["global"].setdefault(key, {})
                _backfill_installed_as(data)
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return _empty_manifest()


def save_manifest(manifest: dict, path: Path) -> None:
    """Write the manifest to disk, updating the updatedAt timestamp."""
    manifest["updatedAt"] = _now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _get_scope_dict(manifest: dict, scope: str) -> dict:
    """Return the scope dict for 'global' or a repo absolute path."""
    if scope == "global":
        return manifest["global"]
    if scope not in manifest["repos"]:
        manifest["repos"][scope] = _empty_scope()
    return manifest["repos"][scope]


def record_install(
    manifest: dict,
    scope: str,
    item_type: str,
    name: str,
    version: str,
    content_hash: Optional[str] = None,
    installed_as: str = "explicit",
) -> None:
    """Record an install of a skill, rule, or agent."""
    scope_dict = _get_scope_dict(manifest, scope)
    prev = scope_dict[item_type].get(name)
    if item_type == "skills":
        scope_dict[item_type][name] = build_skill_manifest_item(
            version=version,
            content_hash=content_hash or "",
            installed_at=_now_iso(),
            previous=prev if isinstance(prev, dict) else None,
            installed_as=installed_as,
        )
        return
    scope_dict[item_type][name] = {
        "version": version,
        "contentHash": content_hash or "",
        "installedAt": _now_iso(),
    }


def record_mcp_install(
    manifest: dict,
    scope: str,
    name: str,
    version: str,
    package: str = "",
) -> None:
    """Record an MCP server install, including the pip/npm package name."""
    scope_dict = _get_scope_dict(manifest, scope)
    scope_dict["mcps"][name] = {
        "version": version,
        "installedAt": _now_iso(),
        "package": package,
    }


def remove_install(manifest: dict, scope: str, item_type: str, name: str) -> None:
    """Remove an installed item from the manifest."""
    scope_dict = _get_scope_dict(manifest, scope)
    scope_dict[item_type].pop(name, None)


def get_installed(manifest: dict, scope: str, item_type: str) -> dict:
    """Get all installed items of a given type in a scope."""
    scope_dict = _get_scope_dict(manifest, scope)
    return dict(scope_dict.get(item_type, {}))


def get_all_repo_scopes(manifest: dict) -> list[str]:
    """List all repo absolute paths tracked in the manifest."""
    return list(manifest.get("repos", {}).keys())


def migrate_v1_to_v2(v1_path: Path) -> dict:
    """Migrate a v1 manifest (skills-only, flat) to v2 structure."""
    v2 = _empty_manifest()
    if not v1_path.exists():
        return v2
    try:
        v1 = json.loads(v1_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return v2
    for name, info in v1.get("skills", {}).items():
        v2["global"]["skills"][name] = {
            "version": info.get("version", "0.0.0"),
            "contentHash": info.get("contentHash", ""),
            "installedAt": info.get("installedAt", _now_iso()),
        }
    return v2


def auto_migrate(v2_path: Path, v1_path: Path) -> dict:
    """Load v2 if it exists, otherwise migrate from v1, otherwise return empty."""
    if v2_path.exists():
        return load_manifest(v2_path)
    if v1_path.exists():
        manifest = migrate_v1_to_v2(v1_path)
        save_manifest(manifest, v2_path)
        return manifest
    return load_manifest(v2_path)


def record_update_check(manifest: dict) -> None:
    """Record that an update check was performed now."""
    manifest["lastUpdateCheck"] = _now_iso()


def is_stale(manifest: dict, max_age_hours: int = 24) -> bool:
    """Check if the manifest's last update check is older than max_age_hours."""
    last_check = manifest.get("lastUpdateCheck")
    if not last_check:
        return True
    try:
        last_dt = datetime.fromisoformat(last_check)
        age = datetime.now(timezone.utc) - last_dt
        return age.total_seconds() > max_age_hours * 3600
    except (ValueError, TypeError):
        return True
