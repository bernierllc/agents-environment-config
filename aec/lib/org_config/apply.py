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


def apply_preferences(policy: EffectivePolicy) -> list[str]:
    """Write the policy's preferences into prefs.json. Returns applied keys."""
    from ..preferences import OPTIONAL_FEATURES, set_preference, set_setting

    applied: list[str] = []
    for key, value in policy.preferences.items():
        if key in OPTIONAL_FEATURES:
            set_preference(key, bool(value))
        else:
            set_setting(key, value)
        applied.append(key)
    return applied


def apply_prompts(policy: EffectivePolicy) -> None:
    """Register the policy's prompt answers so the prompt() seam pre-answers."""
    from ..prompts import set_overlay_answers

    set_overlay_answers(dict(policy.prompts))


_INSTALL_STANCES = frozenset({"required", "recommended", "pinned"})
_PLURAL_TO_SINGULAR = {"skills": "skill", "rules": "rule", "agents": "agent", "mcps": "mcp"}


def compile_desired_items(policy: EffectivePolicy, scope: str) -> list:
    """Desired-state items for install-intent stances (required/recommended/pinned)."""
    from ..apply_core import DesiredItem

    desired: list = []
    for subject, (_org_id, p) in sorted(policy.items.items()):
        plural, name = subject.split("/", 1)
        if p.stance.value not in _INSTALL_STANCES:
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
        if p.stance.value == "blocked":
            plural, name = subject.split("/", 1)
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

    applied = len(result.applied)
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
    _print_policy_plan(policy)
    try:
        return input("Apply this org policy? [y/N]: ").strip().lower() == "y"
    except EOFError:
        return False
