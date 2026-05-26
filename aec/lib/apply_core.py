"""Shared declarative install-execution core.

Turns a desired-state item list into filesystem + manifest mutations by reusing
the existing install primitives. This is the single seam that ``aec apply``
drives today, and that org-config overlay and package install reuse later, so
there is exactly one engine that installs items from a declarative source.
"""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .console import Console
from .filesystem import installed_dst_path
from .installed_store import record_item_install
from .manifest_v2 import get_installed, load_manifest, record_mcp_install, save_manifest
from .mcp_settings import get_settings_path, write_mcp_server
from .scope import Scope
from .skills_manifest import version_is_newer

TYPE_TO_PLURAL = {"skill": "skills", "rule": "rules", "agent": "agents", "mcp": "mcps"}


@dataclass(frozen=True)
class DesiredItem:
    """One item of desired state, scope-qualified."""

    item_type: str  # "skill" | "rule" | "agent" | "mcp"
    name: str
    scope: str  # "global" or an absolute repo-path string
    version_spec: str = "latest"  # "latest" or an exact version
    package: str = ""  # mcp only


@dataclass
class ApplyPlanEntry:
    item: DesiredItem
    action: str  # "install" | "upgrade" | "noop" | "skip-missing"
    from_version: Optional[str] = None
    to_version: Optional[str] = None
    reason: str = ""


@dataclass
class ApplyResult:
    applied: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def plan_apply(items, *, manifest: dict, available_by_type: dict) -> list:
    """Compare desired items against current state. Pure: no side effects on disk."""
    plan = []
    for item in items:
        plural = TYPE_TO_PLURAL.get(item.item_type)
        if plural is None:
            plan.append(ApplyPlanEntry(item, "skip-missing", reason=f"unknown type '{item.item_type}'"))
            continue
        avail = available_by_type.get(plural, {})
        if item.name not in avail:
            plan.append(ApplyPlanEntry(item, "skip-missing", reason="not in catalog"))
            continue
        avail_version = avail[item.name].get("version", "0.0.0")
        installed = get_installed(manifest, item.scope, plural).get(item.name)
        if not installed:
            plan.append(ApplyPlanEntry(item, "install", None, avail_version, "not installed"))
            continue
        installed_version = installed.get("version", "0.0.0") if isinstance(installed, dict) else "0.0.0"
        if installed_version == avail_version:
            plan.append(ApplyPlanEntry(item, "noop", installed_version, avail_version, "up to date"))
            continue
        newer = False
        if item.item_type != "mcp":
            try:
                newer = version_is_newer(avail_version, installed_version)
            except (ValueError, TypeError):
                newer = False
        if newer:
            plan.append(ApplyPlanEntry(item, "upgrade", installed_version, avail_version, "newer in catalog"))
        else:
            plan.append(
                ApplyPlanEntry(item, "noop", installed_version, avail_version, "installed differs from catalog; keeping")
            )
    return plan


def execute_apply(
    plan,
    *,
    source_dirs: dict,
    available_by_type: dict,
    manifest_path: Path,
    install_hooks: bool = True,
) -> ApplyResult:
    """Execute a plan, mutating the filesystem and the install-state manifest."""
    from ..commands.install_cmd import _install_single_item

    result = ApplyResult()
    for entry in plan:
        if entry.action not in ("install", "upgrade"):
            result.skipped.append(entry)
            continue
        item = entry.item
        plural = TYPE_TO_PLURAL[item.item_type]
        item_info = available_by_type.get(plural, {}).get(item.name)
        if item_info is None:
            result.errors.append((entry, "item disappeared from catalog"))
            continue
        source_dir = source_dirs.get(plural)
        if not source_dir:
            result.errors.append((entry, f"no source directory for {plural}"))
            continue
        scope_obj = _scope_from_key(item.scope)
        try:
            if item.item_type == "mcp":
                _apply_mcp(item, scope_obj, item_info, Path(source_dir), manifest_path)
            else:
                target_dir = getattr(scope_obj, f"{plural}_dir")
                src = Path(source_dir) / item_info.get("path", item.name)
                dst = installed_dst_path(target_dir, item.name, src)
                _install_single_item(
                    item_type=item.item_type,
                    plural=plural,
                    name=item.name,
                    src=src,
                    dst=dst,
                    target_dir=target_dir,
                    scope_key=item.scope,
                    manifest_file=manifest_path,
                    item_info=item_info,
                )
                if install_hooks and not scope_obj.is_global and scope_obj.repo_path is not None:
                    _install_item_hooks(item, scope_obj, item_info, dst)
            result.applied.append(entry)
        except Exception as exc:  # noqa: BLE001 — one bad item must not abort the rest
            result.errors.append((entry, str(exc)))
    return result


def _scope_from_key(scope_key: str) -> Scope:
    if scope_key == "global":
        return Scope(is_global=True, repo_path=None)
    return Scope(is_global=False, repo_path=Path(scope_key))


def _install_item_hooks(item: DesiredItem, scope_obj: Scope, item_info: dict, dst: Path) -> None:
    try:
        from .hooks.lifecycle import install_hooks_for_item

        install_hooks_for_item(
            item_type=item.item_type,
            item_key=item.name,
            item_version=item_info.get("version", "0.0.0"),
            item_dir=dst,
            repo_root=scope_obj.repo_path,
            allow_custom_check=True,
        )
    except Exception as exc:  # noqa: BLE001 — never fail an install on hook wiring
        Console.warning(f"hooks install failed for {item.name}: {exc}")


def _apply_mcp(
    item: DesiredItem,
    scope_obj: Scope,
    item_info: dict,
    source_dir: Path,
    manifest_path: Path,
) -> None:
    mcp_file = source_dir / item_info["path"] / "mcp.json"
    mcp_def = json.loads(mcp_file.read_text(encoding="utf-8"))
    pip_package = mcp_def.get("install", {}).get("pip", "")
    if pip_package:
        subprocess.run(["pip", "install", pip_package])
    settings_path = get_settings_path(scope_obj)
    for server_name, server_entry in mcp_def.get("mcpServers", {}).items():
        write_mcp_server(settings_path, server_name, server_entry)
    manifest = load_manifest(manifest_path)
    record_mcp_install(manifest, item.scope, item.name, item_info.get("version", "0.0.0"), pip_package)
    save_manifest(manifest, manifest_path)
    record_item_install("mcp", item.name, item_info.get("version", "0.0.0"))
