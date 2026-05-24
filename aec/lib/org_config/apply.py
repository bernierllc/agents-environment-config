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

from .effective import EffectivePolicy


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
