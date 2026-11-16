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

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .effective import EffectivePolicy, effective_policy
from .errors import OrgApplyCommittedError, OrgConfigError
from .paths import OrgPaths
from .schema import RESERVED_SOURCE_IDS, source_identity

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


def apply_prompts(policy: EffectivePolicy, paths: Optional[OrgPaths] = None) -> None:
    """Register the policy's prompt answers so the prompt() seam pre-answers.

    With ``paths`` (the real ``aec org apply``), also persist exactly these answers as
    the approved set that later commands load. Only this function writes that file, so
    enrolling, refreshing or re-enrolling a config can never change what is trusted.
    """
    from ..atomic_write import atomic_write_text
    from ..prompts import set_overlay_answers
    from .discovery import discover_enrolled_orgs

    answers = dict(policy.prompts)
    set_overlay_answers(answers)
    if paths is not None:
        org_ids = sorted(e.config.org_id for e in discover_enrolled_orgs(paths))
        atomic_write_text(paths.approved_prompts, json.dumps({"org_ids": org_ids, "answers": answers}, indent=2))


def load_enrolled_prompt_answers(paths: OrgPaths) -> int:
    """Pre-answer prompts from the answers a person approved with ``aec org apply``.

    ``set_overlay_answers`` only lives for one process, so every command other than
    ``aec org apply`` (``aec repo setup``) calls this at startup. Returns the count loaded.

    Reads only the approved-answers file, never the enrolled configs. The answers are
    dropped when any org that contributed to them has since been unenrolled.
    """
    from ..prompts import set_overlay_answers

    if not paths.approved_prompts.exists():
        return 0
    approved = json.loads(paths.approved_prompts.read_text())
    if not all(paths.config_for(org_id).exists() for org_id in approved["org_ids"]):
        return 0
    set_overlay_answers(approved["answers"])
    return len(approved["answers"])


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
    for subject, (org_id, p) in sorted(policy.items.items()):
        plural, name = subject.split("/", 1)
        if plural == "plugins" or p.stance.value not in _INSTALL_STANCES:
            continue
        desired.append(
            DesiredItem(
                item_type=_PLURAL_TO_SINGULAR[plural],
                name=name,
                scope=scope,
                version_spec=p.version or "latest",
                source_id="" if p.source in RESERVED_SOURCE_IDS else source_identity(org_id, p.source),
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


def plan_items(
    policy: EffectivePolicy,
    scope: str,
    *,
    available_by_type: dict,
    manifest_path,
    source_commits: Optional[dict] = None,
) -> list:
    """Plan the install-intent items (pure; ``execute_apply`` runs the plan).
    Blocked removals are not planned: they run after the commit point
    (``remove_blocked_items``). ``source_commits`` maps a custom source key
    (``"<org_id>/<id>"``) to the commit being applied."""
    import dataclasses

    from ..apply_core import plan_apply
    from ..manifest_v2 import load_manifest

    commits = source_commits or {}
    desired = [
        dataclasses.replace(i, source_commit=commits.get(i.source_id, ""))
        for i in compile_desired_items(policy, scope)
    ]
    return plan_apply(desired, manifest=load_manifest(manifest_path), available_by_type=available_by_type)


def _failure(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def remove_blocked_items(
    policy: EffectivePolicy, scope: str, *, manifest_path
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Uninstall blocked items still in the manifest (so a retry skips finished ones).

    Returns ``(removed_keys, errors)``; ``errors`` holds ``(subject, message)`` per
    failed item and the loop continues past one. ``SystemExit`` is caught because
    the uninstall command exits on some failures; it is reported, not swallowed.
    """
    from ..manifest_v2 import get_installed, load_manifest

    removed: list[tuple[str, str]] = []
    errors: list[tuple[str, str]] = []
    for item_type, name in blocked_item_keys(policy):
        if name not in get_installed(load_manifest(manifest_path), scope, item_type + "s"):
            continue
        try:
            _uninstall_blocked(item_type, name, scope)
        except (Exception, SystemExit) as exc:
            errors.append((f"{item_type}s/{name}", _failure(exc)))
        else:
            removed.append((item_type, name))
    return removed, errors


def _uninstall_blocked(item_type: str, name: str, scope: str) -> None:
    from ...commands.uninstall import run_uninstall

    run_uninstall(item_type, name, global_flag=(scope == "global"), yes=True)


def apply_plugins(
    policy: EffectivePolicy,
    scope: str,
    *,
    source_dirs: dict,
    manifest_path,
) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    """Install install-intent plugins and uninstall blocked ones.

    Runs through the same loadout engine as ``aec apply`` (``install_plugin`` /
    ``uninstall_plugin``), so ``plugins.execution=instructions-only`` still
    prints instead of running. Versions are whatever the agent's plugin manager
    reports (``installed_record``). Returns ``(installed, removed, errors)``:
    names, plus ``(subject, message)`` per failed plugin (the loop continues past
    one; ``SystemExit`` is caught because the uninstall command exits on some failures).
    """
    import subprocess

    from ..config import detect_agents
    from ..console import Console
    from ..loadout import LoadoutError, load_loadout
    from ..manifest_v2 import get_installed, load_manifest
    from ..plugin_install import install_and_record
    from ..preferences import get_setting
    from ..sources import discover_available

    want = _plugin_names(policy, _INSTALL_STANCES)
    blocked = _plugin_names(policy, {"blocked"})
    installed_names: list[str] = []
    removed_names: list[str] = []
    errors: list[tuple[str, str]] = []

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
        try:
            install_and_record(
                manifest_def, scope, name, detected,
                runner=lambda cmd: subprocess.run(cmd),
                confirm=lambda *a: True, printer=Console.print, pref=pref,
                manifest_path=manifest_path,
            )
        except (Exception, SystemExit) as exc:
            errors.append((f"plugins/{name}", _failure(exc)))
        else:
            installed_names.append(name)

    for name in blocked:
        if name in get_installed(load_manifest(manifest_path), scope, "plugins"):
            try:
                _uninstall_blocked("plugin", name, scope)
            except (Exception, SystemExit) as exc:
                errors.append((f"plugins/{name}", _failure(exc)))
            else:
                removed_names.append(name)

    return installed_names, removed_names, errors


@dataclass
class ApplyOutcome:
    applied_items: int
    removed_items: int
    held: tuple[str, ...]
    preferences_applied: list
    # "locked" | "declined" | "dry-run" | "source_failed" | "install_failed" | None
    skipped_reason: Optional[str] = None
    # (subject, message) for removals/plugin commands that failed AFTER the apply was
    # committed. The apply still counts as applied; the caller must exit non-zero.
    item_errors: list = field(default_factory=list)


@dataclass(frozen=True)
class SyncedSource:
    org_id: str
    source_id: str
    commit: str
    contributes: tuple[str, ...]
    # Staged checkout this apply installs from; published by publish_sources.
    staged: Path

    @property
    def key(self) -> str:
        return f"{self.org_id}/{self.source_id}"


def _staging_dir(paths, org_id: str, source_id: str) -> Path:
    return paths.org_dir_for(org_id) / "sources.next" / source_id


def sync_custom_sources(paths) -> Optional[list[SyncedSource]]:
    """Check out every enrolled org's custom sources before anything is written.

    Each source is checked out into a staging dir at its ``commit`` pin, else the
    commit last approved for it, else (first apply) the tip of its ref. The live
    checkout at ``<org_id>.d/sources/<id>/`` (what outdated/upgrade read) only
    changes in ``publish_sources``, after the whole apply succeeds. Returns None,
    after printing why and discarding staged checkouts, if any source fails.
    """
    from ..console import Console
    from .discovery import discover_enrolled_orgs
    from .git_source import sync_source
    from .state import read_state

    synced: list[SyncedSource] = []
    staged_dirs: list[Path] = []
    for enrolled in discover_enrolled_orgs(paths):
        cfg = enrolled.config
        if not cfg.custom_sources:
            continue
        st = read_state(paths, cfg.org_id)
        approved = (st.source_commits if st else None) or {}
        for cs in cfg.custom_sources:
            want = cs.commit or approved.get(cs.id)
            staged = _staging_dir(paths, cfg.org_id, cs.id)
            staged_dirs.append(staged)
            try:
                commit = sync_source(cs.url, cs.ref, want, staged)
                synced.append(SyncedSource(cfg.org_id, cs.id, commit, cs.contributes, staged))
                _check_item_paths(synced[-1])
            except OrgConfigError as exc:
                Console.error(
                    f"org-config apply stopped: source {cfg.org_id}/{cs.id} failed: {exc}. "
                    "Nothing was applied."
                )
                discard_staged(staged_dirs)
                return None
    return synced


def _check_item_paths(s: SyncedSource) -> None:
    """Refuse items whose files leave the checkout or include symlinks.

    The pinned commit authenticates only the repo's own bytes; a path or link
    pointing outside it would install files from this machine instead.
    """
    from ..confine import item_name_problem
    from ..sources import discover_available, get_source_dirs
    from .errors import OrgConfigValidationError

    root = s.staged.resolve()
    dirs = get_source_dirs(s.staged)
    for plural in s.contributes:
        d = dirs[plural]
        if not d.exists():
            continue
        for name, info in discover_available(d, plural).items():
            if (problem := item_name_problem(plural, name)) is not None:
                raise OrgConfigValidationError(
                    f"{plural[:-1]} in source: {problem}", field_path=f"sources.custom.{s.source_id}"
                )
            p = d / str(info.get("path", name))
            members = [p, *(p.rglob("*") if p.is_dir() and not p.is_symlink() else ())]
            if any(m.is_symlink() for m in members) or not p.resolve().is_relative_to(root):
                raise OrgConfigValidationError(
                    f"{plural[:-1]} '{name}' points outside the source repo or contains a symlink",
                    field_path=f"sources.custom.{s.source_id}",
                )


def discard_staged(dirs) -> None:
    for d in dirs:
        shutil.rmtree(d, ignore_errors=True)  # best-effort: the next apply re-stages it


def publish_sources(paths, synced: list[SyncedSource], commit_state: Callable[[], None]) -> None:
    """Make each staged checkout live, then ``commit_state()``; all or nothing.

    Live checkouts move aside to ``sources.prev`` first, so any failure (a rename
    or the approval-state write) puts every one back and leaves nothing approved.
    """
    done = []  # (live, prev or None), in publish order
    try:
        for s in synced:
            live = paths.source_dir_for(s.org_id, s.source_id)
            prev = live.parent.parent / "sources.prev" / s.source_id
            live.parent.mkdir(parents=True, exist_ok=True)
            prev.parent.mkdir(parents=True, exist_ok=True)
            if prev.exists():
                shutil.rmtree(prev)  # left by an interrupted earlier publish
            if live.exists():
                live.rename(prev)
                done.append((live, prev))
            else:
                done.append((live, None))
            s.staged.rename(live)
        commit_state()
    except Exception:
        for live, prev in reversed(done):
            if live.exists():
                shutil.rmtree(live)
            if prev is not None:
                prev.rename(live)
        discard_staged(s.staged for s in synced)
        raise
    for _, prev in done:
        if prev is not None:
            shutil.rmtree(prev, ignore_errors=True)  # best-effort: the next publish clears it


def _catalog(paths, synced: list[SyncedSource], published: bool = False):
    """Source dirs and available items: AEC catalog keyed by plural, custom
    sources keyed by ``("<org_id>/<id>", plural)``. Custom sources read from their
    staged checkout, or from the live one once ``publish_sources`` has run."""
    from ..sources import discover_available, get_source_dirs

    manifest_path = Path.home() / ".agents-environment-config" / "installed-manifest.json"
    source_dirs: dict = dict(get_source_dirs())
    available: dict = {}
    for plural in ("skills", "rules", "agents", "mcps"):
        d = source_dirs.get(plural)
        if d and Path(d).exists():
            available[plural] = discover_available(d, plural)
    for s in synced:
        clone_dirs = get_source_dirs(paths.source_dir_for(s.org_id, s.source_id) if published else s.staged)
        for plural in s.contributes:
            d = clone_dirs[plural]
            key = (s.key, plural)
            source_dirs[key] = d
            available[key] = discover_available(d, plural) if d.exists() else {}
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
    on_commit: Optional[Callable[[], None]] = None,
) -> ApplyOutcome:
    """Apply effective org policy to the environment.

    ``on_commit`` runs once, right after publish + stamp: the caller releases its
    undo state (a snapshot left on disk by a killed process is rolled back by the
    next reader, which would erase the stamp and its marker).

    Refuses while any org's signing key is in rotation lockout. Managed mode
    applies silently; guided mode shows the plan and asks for confirmation.
    """
    from ..console import Console
    from .propagation import run_propagation_gate

    gate =run_propagation_gate(paths, now=now, pubkey_fetcher=pubkey_fetcher)
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

    synced = sync_custom_sources(paths)
    if synced is None:
        return ApplyOutcome(0, 0, policy.held, [], skipped_reason="source_failed")

    # Plan against the staged checkouts (pure: nothing is written), so an item the
    # catalog cannot satisfy stops the apply before anything is published.
    source_dirs, available_by_type, manifest_path = _catalog(paths, synced)
    plan = plan_items(
        policy,
        scope,
        available_by_type=available_by_type,
        manifest_path=manifest_path,
        source_commits={s.key: s.commit for s in synced},
    )
    # A required or pinned item the source cannot provide (unsatisfiable, or missing from
    # the catalog) must never be approved; only a merely recommended one may be skipped.
    unsatisfiable = [
        e for e in plan
        if e.action == "unsatisfiable"
        or (e.action == "skip-missing" and _mandatory(policy, e.item))
    ]
    if unsatisfiable:
        for entry in unsatisfiable:
            Console.error(f"org-config apply: {entry.item.item_type} '{entry.item.name}' failed: {entry.reason}")
        Console.error("org-config apply failed; source commits and pending reviews were not approved.")
        discard_staged(s.staged for s in synced)
        return ApplyOutcome(0, 0, policy.held, [], skipped_reason="install_failed")

    # The stamp is the commit point and nothing is installed before it: if publishing
    # or stamping fails, the caller's restore of config, checkouts and state to the
    # approved version is the whole undo, because nothing else has changed.
    try:
        publish_sources(paths, synced, lambda: _stamp_applied(paths, now, synced))
    except (OSError, OrgConfigError) as exc:
        Console.error(f"org-config apply: could not publish custom sources: {exc}")
        Console.error("org-config apply failed; source commits and pending reviews were not approved.")
        return ApplyOutcome(0, 0, policy.held, [], skipped_reason="install_failed")

    # Committed. Whatever escapes from here is a post-commit failure: it is re-raised as
    # OrgApplyCommittedError so no caller can mistake it for a pre-commit one and restore
    # over the published sources. The stamp already left an apply_failed marker.
    try:
        if on_commit is not None:
            on_commit()  # the caller's undo is void from here; a kill must not trigger it either
        return _apply_committed(paths, policy, scope, plan, synced)
    except BaseException as exc:  # incl. Ctrl-C/SystemExit: the commit stands either way
        raise OrgApplyCommittedError(
            f"org-config apply was committed but did not finish ({type(exc).__name__}: {exc}); "
            "run `aec org apply` to retry"
        ) from exc


def _apply_committed(paths, policy: EffectivePolicy, scope: str, plan, synced: list[SyncedSource]) -> ApplyOutcome:
    """Everything after the commit point. Every failure is reported and recorded per
    item; the next apply recomputes the plan and retries what is still missing."""
    from ..apply_core import execute_apply
    from ..console import Console

    source_dirs, available_by_type, manifest_path = _catalog(paths, synced, published=True)
    errors: list[tuple[str, str]] = []
    prefs_applied: list[str] = []
    try:
        prefs_applied = apply_preferences(policy)
        apply_prompts(policy, paths)
    except (Exception, SystemExit) as exc:  # same per-item catch as uninstalls: recorded, never raised past the stamp
        errors.append(("preferences", _failure(exc)))
    result = execute_apply(
        plan,
        source_dirs=source_dirs,
        available_by_type=available_by_type,
        manifest_path=manifest_path,
    )
    errors += [(f"{e.item.item_type}s/{e.item.name}", msg) for e, msg in result.errors]
    removed, remove_errors = remove_blocked_items(policy, scope, manifest_path=manifest_path)
    plugins_in, plugins_out, plugin_errors = apply_plugins(
        policy, scope, source_dirs=source_dirs, manifest_path=manifest_path
    )
    errors += remove_errors + plugin_errors
    removed += [("plugin", n) for n in plugins_out]
    applied = len(result.applied) + len(plugins_in)
    Console.success(
        f"Org policy applied: {applied} installed, {len(removed)} removed, "
        f"{len(prefs_applied)} preference(s) set."
    )
    if policy.held:
        Console.warning(
            f"{len(policy.held)} item(s) held pending decision — run `aec org resolve`."
        )
    if errors:
        for subject, message in errors:
            Console.error(f"org-config apply: {subject} failed after the policy was applied: {message}")
        Console.error("Run `aec org apply` to retry the failed items.")
    # Only here does the stamp's in-progress marker give way: to the per-item failures,
    # or to nothing when every post-stamp step succeeded. If this write itself fails,
    # the marker stays and the next apply retries.
    _settle_apply_marker(paths, policy, errors)
    return ApplyOutcome(
        applied_items=applied,
        removed_items=len(removed),
        held=policy.held,
        preferences_applied=prefs_applied,
        item_errors=errors,
    )


def _mandatory(policy: EffectivePolicy, item) -> bool:
    """Whether the policy requires or pins this item (so it cannot be skipped)."""
    owner = policy.items.get(f"{item.item_type}s/{item.name}")
    return owner is not None and owner[1].stance.value in ("required", "pinned")


def _settle_apply_marker(paths, policy: EffectivePolicy, errors: list[tuple[str, str]]) -> None:
    """Replace the stamp's in-progress ``apply_failed`` marker once the post-commit work ran.

    An org owning failed items gets them recorded as ``apply_failed``, so ``aec update``
    and ``pending_fix`` keep saying so until an apply succeeds; an org with none has the
    marker cleared. A preference is merged across orgs and has no single owner, so it is
    recorded on every enrolled org."""
    import dataclasses

    from .discovery import discover_enrolled_orgs
    from .state import read_state, write_state

    by_org: dict[str, list[dict]] = {}
    for subject, message in errors:
        owners = (
            [policy.items[subject][0]]
            if subject in policy.items
            else [e.config.org_id for e in discover_enrolled_orgs(paths)]
        )
        for org_id in owners:
            by_org.setdefault(org_id, []).append({"item": subject, "error": message})
    for enrolled in discover_enrolled_orgs(paths):
        org_id = enrolled.config.org_id
        st = read_state(paths, org_id)
        pending = (st.pending if st else None) or {}
        # A trust change is never downgraded (same rule as _set_pending).
        if st is None or pending.get("kind") == "trust_change":
            continue
        items = by_org.get(org_id)
        if items:
            write_state(paths, dataclasses.replace(st, pending={
                "kind": "apply_failed",
                "reason": f"{len(items)} item(s) failed to apply: " + ", ".join(i["item"] for i in items),
                "items": items,
            }))
        elif pending.get("kind") == "apply_failed":
            write_state(paths, dataclasses.replace(st, pending=None))


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


def _stamp_applied(paths, now: Optional[str], synced: list[SyncedSource] = ()) -> None:
    """Record ``last_applied_at`` and applied source commits on every enrolled org, and in
    the same write mark the apply as in progress (``apply_failed``), so a process killed
    before the post-stamp installs finish leaves a marker the next ``aec update`` or
    ``aec org apply`` sees. ``_settle_apply_marker`` clears it on full completion. A
    ``review``/``verify_failed``/``trust_change`` pending is left as it is.

    All or nothing: if one org's write fails, every org's state is put back
    (by rename, so it works on a full disk too).
    """
    import dataclasses
    from datetime import datetime, timezone

    from .discovery import discover_enrolled_orgs
    from .state import all_or_nothing, read_state, write_state

    stamp = now or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    orgs = discover_enrolled_orgs(paths)
    with all_or_nothing(paths, [e.config.org_id for e in orgs]):
        for enrolled in orgs:
            org_id = enrolled.config.org_id
            st = read_state(paths, org_id)
            if st is not None:
                commits = {s.source_id: s.commit for s in synced if s.org_id == org_id} or None
                pending = st.pending
                if not pending or pending.get("kind") == "apply_failed":
                    pending = {
                        "kind": "apply_failed",
                        "reason": "apply interrupted before every install finished",
                        "items": [],
                    }
                write_state(paths, dataclasses.replace(
                    st, last_applied_at=stamp, source_commits=commits, pending=pending,
                ))
