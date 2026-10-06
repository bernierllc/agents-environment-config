"""Apply effective org policy to the user's environment.

Translates an :class:`EffectivePolicy` (already merged + conflict-resolved) into
real changes by reusing existing engines:

  * preferences  -> ``aec.lib.preferences`` (settings / optional_rules sections)
  * prompts      -> ``aec.lib.prompts`` overlay-answer registry
  * items        -> ``aec.lib.apply_core`` (install) + uninstall (block)

Higher-level orchestration (mode, lockout, CLI) lives in later tasks; this
module holds the category appliers.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .effective import EffectivePolicy, effective_policy


_CI_PREFIX = "configurable_instructions."


def apply_preferences(policy: EffectivePolicy) -> list[str]:
    """Write the policy's preferences into the right prefs.json section.

    Routing: ``optional_rules`` (OPTIONAL_FEATURES keys) ->
    ``configurable_instructions.<key>.<agent>`` (dotted namespace) ->
    ``settings`` (everything else). Returns the keys applied.
    """
    from ..preferences import (
        OPTIONAL_FEATURES,
        get_instruction_config,
        set_instruction_config,
        set_preference,
        set_setting,
    )

    applied: list[str] = []
    instruction_agents: dict[str, dict[str, bool]] = {}
    for key, value in policy.preferences.items():
        if key in OPTIONAL_FEATURES:
            set_preference(key, bool(value))
        elif key.startswith(_CI_PREFIX):
            parts = key.split(".")
            if len(parts) == 3:
                _, instruction_key, agent_key = parts
                instruction_agents.setdefault(instruction_key, {})[agent_key] = bool(value)
            else:
                set_setting(key, value)
        else:
            set_setting(key, value)
        applied.append(key)

    for instruction_key, agents in instruction_agents.items():
        merged = {**(get_instruction_config(instruction_key) or {}), **agents}
        set_instruction_config(instruction_key, merged)

    return applied


def apply_prompts(policy: EffectivePolicy) -> None:
    """Register the policy's prompt answers so the prompt() seam pre-answers."""
    from ..prompts import set_overlay_answers

    set_overlay_answers(dict(policy.prompts))


_INSTALL_STANCES = frozenset({"required", "recommended", "pinned"})
# File-copy item types applied through apply_core. Plugins install through the
# loadout engine instead (see apply_plugins), so they are deliberately absent.
_PLURAL_TO_SINGULAR = {"skills": "skill", "rules": "rule", "agents": "agent", "mcps": "mcp"}


def _plugin_names(policy: EffectivePolicy, stances) -> list[str]:
    return [
        subject.split("/", 1)[1]
        for subject, (_org_id, p) in sorted(policy.items.items())
        if subject.startswith("plugins/") and p.stance.value in stances
    ]


def compile_desired_items(policy: EffectivePolicy, scope: str) -> list:
    """Desired-state items for install-intent stances (required/recommended/pinned)."""
    from ..apply_core import DesiredItem

    desired: list = []
    for subject, (_org_id, p) in sorted(policy.items.items()):
        plural, name = subject.split("/", 1)
        if plural == "plugins" or p.stance.value not in _INSTALL_STANCES:
            continue
        desired.append(
            DesiredItem(
                item_type=_PLURAL_TO_SINGULAR[plural],
                name=name,
                scope=scope,
                version_spec=p.version or "latest",
            )
        )
    return desired


def blocked_item_keys(policy: EffectivePolicy) -> list[tuple[str, str]]:
    """(item_type, name) pairs the policy blocks, for removal."""
    out: list[tuple[str, str]] = []
    for subject, (_org_id, p) in sorted(policy.items.items()):
        plural, name = subject.split("/", 1)
        if p.stance.value == "blocked" and plural != "plugins":
            out.append((_PLURAL_TO_SINGULAR[plural], name))
    return out


def apply_items(
    policy: EffectivePolicy,
    scope: str,
    *,
    source_dirs: dict,
    available_by_type: dict,
    manifest_path,
    install_hooks: bool = True,
):
    """Install install-intent items and remove blocked ones. Returns
    ``(ApplyResult, removed_keys)``."""
    from ..apply_core import execute_apply, plan_apply
    from ..manifest_v2 import get_installed, load_manifest

    desired = compile_desired_items(policy, scope)
    manifest = load_manifest(manifest_path)
    plan = plan_apply(desired, manifest=manifest, available_by_type=available_by_type)
    result = execute_apply(
        plan,
        source_dirs=source_dirs,
        available_by_type=available_by_type,
        manifest_path=manifest_path,
        install_hooks=install_hooks,
    )

    removed: list[tuple[str, str]] = []
    for item_type, name in blocked_item_keys(policy):
        plural = item_type + "s"
        installed = get_installed(load_manifest(manifest_path), scope, plural)
        if name in installed:
            _uninstall_blocked(item_type, name, scope)
            removed.append((item_type, name))
    return result, removed


def _uninstall_blocked(item_type: str, name: str, scope: str) -> None:
    from ...commands.uninstall import run_uninstall

    run_uninstall(item_type, name, global_flag=(scope == "global"), yes=True)


def apply_plugins(
    policy: EffectivePolicy,
    scope: str,
    *,
    source_dirs: dict,
    manifest_path,
) -> tuple[list[str], list[str]]:
    """Install install-intent plugins and uninstall blocked ones.

    Runs through the same loadout engine as ``aec apply`` (``install_plugin`` /
    ``uninstall_plugin``), so ``plugins.execution=instructions-only`` still
    prints instead of running. Versions are whatever the agent's plugin manager
    reports (``installed_record``). Returns ``(installed, removed)`` names.
    """
    import subprocess

    from ..claude_plugins import installed_record
    from ..config import detect_agents
    from ..console import Console
    from ..installed_store import record_item_install
    from ..loadout import LoadoutError, load_loadout
    from ..manifest_v2 import get_installed, load_manifest, record_plugin_install, save_manifest
    from ..plugin_install import install_plugin
    from ..preferences import get_setting
    from ..sources import discover_available

    want = _plugin_names(policy, _INSTALL_STANCES)
    blocked = _plugin_names(policy, {"blocked"})
    installed_names: list[str] = []
    removed_names: list[str] = []

    source_dir = source_dirs.get("plugins")
    available = (
        discover_available(Path(source_dir), "plugins")
        if source_dir and Path(source_dir).exists()
        else {}
    )
    pref = get_setting("plugins.execution")
    detected = detect_agents()

    for name in want:
        if name in get_installed(load_manifest(manifest_path), scope, "plugins"):
            continue
        if name not in available:
            Console.warning(f"Org policy plugin not in catalog: {name}; skipping.")
            continue
        try:
            manifest_def = load_loadout(Path(source_dir) / available[name]["path"])
        except LoadoutError as exc:
            Console.warning(f"Invalid plugin '{name}': {exc}; skipping.")
            continue
        # The org policy was approved up front; external plugins never run anyway.
        result = install_plugin(
            manifest_def, detected,
            runner=lambda cmd: subprocess.run(cmd),
            confirm=lambda *a: True, printer=Console.print, pref=pref,
        )
        version, plugin_id = installed_record(manifest_def, result)
        manifest = load_manifest(manifest_path)
        record_plugin_install(
            manifest, scope, name, version,
            install_type=result["install_type"], targets=result["targets"],
            plugin_id=plugin_id,
        )
        save_manifest(manifest, manifest_path)
        record_item_install("plugin", name, version)
        installed_names.append(name)

    for name in blocked:
        if name in get_installed(load_manifest(manifest_path), scope, "plugins"):
            _uninstall_blocked("plugin", name, scope)
            removed_names.append(name)

    return installed_names, removed_names


@dataclass
class ApplyOutcome:
    applied_items: int
    removed_items: int
    held: tuple[str, ...]
    preferences_applied: list
    skipped_reason: Optional[str] = None  # "locked" | "declined" | "dry-run" | None


def _catalog(scope: str):
    from ..config import get_repo_root  # noqa: F401 - imported for side-effect parity
    from ..sources import discover_available, get_source_dirs

    manifest_path = Path.home() / ".agents-environment-config" / "installed-manifest.json"
    source_dirs: dict = {}
    available: dict = {}
    try:
        source_dirs = get_source_dirs()
        for plural in ("skills", "rules", "agents", "mcps"):
            d = source_dirs.get(plural)
            if d and Path(d).exists():
                available[plural] = discover_available(d, plural)
    except Exception:  # noqa: BLE001 - missing catalog just means nothing installs
        source_dirs, available = {}, {}
    return source_dirs, available, manifest_path


def apply_org_policy(
    paths,
    *,
    scope: str = "global",
    mode_override: Optional[str] = None,
    dry_run: bool = False,
    confirm: Optional[Callable[[EffectivePolicy], bool]] = None,
    now: Optional[str] = None,
    pubkey_fetcher=None,
) -> ApplyOutcome:
    """Apply effective org policy to the environment.

    Refuses while any org's signing key is in rotation lockout. Managed mode
    applies silently; guided mode shows the plan and asks for confirmation.
    """
    from ..console import Console
    from .propagation import run_propagation_gate

    gate = run_propagation_gate(paths, now=now, pubkey_fetcher=pubkey_fetcher)
    if gate.locked:
        Console.error(
            "org-config apply blocked: key rotation locked for "
            f"{', '.join(gate.locked)} (run: aec org trust-rotate)"
        )
        return ApplyOutcome(0, 0, (), [], skipped_reason="locked")

    policy = effective_policy(paths)
    mode = mode_override or policy.install_mode or "guided"

    if dry_run:
        _print_policy_plan(policy)
        return ApplyOutcome(0, 0, policy.held, [], skipped_reason="dry-run")

    if mode == "guided":
        decide = confirm if confirm is not None else _default_confirm
        if not decide(policy):
            Console.info("org-config apply declined.")
            return ApplyOutcome(0, 0, policy.held, [], skipped_reason="declined")

    prefs_applied = apply_preferences(policy)
    apply_prompts(policy)

    source_dirs, available_by_type, manifest_path = _catalog(scope)
    result, removed = apply_items(
        policy,
        scope,
        source_dirs=source_dirs,
        available_by_type=available_by_type,
        manifest_path=manifest_path,
    )

    plugins_in, plugins_out = apply_plugins(
        policy, scope, source_dirs=source_dirs, manifest_path=manifest_path
    )
    applied = len(result.applied) + len(plugins_in)
    removed = [*removed, *plugins_out]
    Console.success(
        f"Org policy applied: {applied} installed, {len(removed)} removed, "
        f"{len(prefs_applied)} preference(s) set."
    )
    if policy.held:
        Console.warning(
            f"{len(policy.held)} item(s) held pending decision — run `aec org resolve`."
        )
    return ApplyOutcome(
        applied_items=applied,
        removed_items=len(removed),
        held=policy.held,
        preferences_applied=prefs_applied,
    )


def _print_policy_plan(policy: EffectivePolicy) -> None:
    from ..console import Console

    Console.print("Org policy plan:")
    for subject, (org_id, p) in sorted(policy.items.items()):
        Console.print(f"  [{p.stance.value}] {subject} (from {org_id})")
    for key, value in sorted(policy.preferences.items()):
        Console.print(f"  [pref] {key}={value}")
    if policy.held:
        Console.warning(f"  held (needs `aec org resolve`): {', '.join(policy.held)}")


def _default_confirm(policy: EffectivePolicy) -> bool:
    from ..prompt_catalog.lifecycle_area import ORG_APPLY_CONFIRM
    from ..prompts import prompt

    _print_policy_plan(policy)
    return prompt(
        ORG_APPLY_CONFIRM,
        "Apply this org policy? [y/N]: ",
        type="yes_no",
        default=False,
    ).strip().lower() == "y"
