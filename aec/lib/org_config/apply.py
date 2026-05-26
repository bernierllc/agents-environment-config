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

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Optional

from .effective import EffectivePolicy, effective_policy, effective_policy_for_repo
from .schema import ITEM_TYPES


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


def detect_current_repo() -> tuple[Optional[str], Optional[str]]:
    """Best-effort (repo_root, origin_remote) for the current working directory."""
    import subprocess

    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:  # noqa: BLE001 - not a repo / no git
        return None, None
    if not root:
        return None, None
    try:
        remote = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:  # noqa: BLE001 - no origin remote
        remote = ""
    return root, (remote or None)


def _profile_subjects(orgs, repo_path, git_remote) -> set:
    from .projects import match_project

    subjects: set = set()
    for e in orgs:
        profile = match_project(e.config.projects, repo_path=repo_path, git_remote=git_remote)
        if profile is None:
            continue
        for item_type in ITEM_TYPES:
            for name in profile.items.get(item_type, {}):
                subjects.add(f"{item_type}/{name}")
    return subjects


def _apply_repo_overlays(paths, now, repo_path, git_remote) -> tuple[int, int]:
    """Apply matching project-profile items at repo scope. Returns (applied, removed).

    Only the items contributed/overridden by a matching profile are applied at
    repo scope; base policy stays global. Profile-introduced cross-org conflicts
    are still held by the repo-effective policy.
    """
    from .discovery import discover_enrolled_orgs

    orgs = discover_enrolled_orgs(paths)
    if not any(e.config.projects for e in orgs):
        return 0, 0
    if repo_path is None and git_remote is None:
        repo_path, git_remote = detect_current_repo()
    if repo_path is None and git_remote is None:
        return 0, 0

    subjects = _profile_subjects(orgs, repo_path, git_remote)
    if not subjects:
        return 0, 0

    repo_policy = effective_policy_for_repo(
        paths, repo_path=repo_path, git_remote=git_remote, now=now
    )
    restricted = {s: v for s, v in repo_policy.items.items() if s in subjects}
    if not restricted:
        return 0, 0

    scope = repo_path
    scoped = replace(repo_policy, items=restricted, preferences={}, prompts={})
    source_dirs, available_by_type, manifest_path = _catalog(scope)
    result, removed = apply_items(
        scoped,
        scope,
        source_dirs=source_dirs,
        available_by_type=available_by_type,
        manifest_path=manifest_path,
    )
    return len(result.applied), len(removed)


def apply_org_policy(
    paths,
    *,
    scope: str = "global",
    mode_override: Optional[str] = None,
    dry_run: bool = False,
    confirm: Optional[Callable[[EffectivePolicy], bool]] = None,
    now: Optional[str] = None,
    pubkey_fetcher=None,
    repo_path: Optional[str] = None,
    git_remote: Optional[str] = None,
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

    policy = effective_policy(paths, now=now)
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

    repo_applied, repo_removed = _apply_repo_overlays(paths, now, repo_path, git_remote)

    applied = len(result.applied) + repo_applied
    total_removed = len(removed) + repo_removed
    Console.success(
        f"Org policy applied: {applied} installed, {total_removed} removed, "
        f"{len(prefs_applied)} preference(s) set."
    )
    if repo_applied or repo_removed:
        Console.info(
            f"  ({repo_applied} installed, {repo_removed} removed at repo scope)"
        )
    if policy.held:
        Console.warning(
            f"{len(policy.held)} item(s) held pending decision — run `aec org resolve`."
        )
    return ApplyOutcome(
        applied_items=applied,
        removed_items=total_removed,
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
