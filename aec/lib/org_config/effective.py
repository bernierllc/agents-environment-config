"""Effective (merged, conflict-resolved) org policy.

Combines every enrolled org's policy into the single view the applier acts on.
Honoring the conflict principles (P2/P7): subjects with an *open* conflict are
held (excluded, never silently resolved); subjects with a *resolved* conflict
take the recorded decision (``honor:<org>`` picks that org's value, ``skip``
drops it); everything unambiguous merges directly.

Pure read: discovers configs and reads the resolutions store, but writes
nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Optional

from .conflicts import detect_conflicts
from .discovery import discover_enrolled_orgs
from .paths import OrgPaths
from .resolutions import input_hash_for, is_valid, load_resolutions
from .schema import ITEM_TYPES, CustomSource, ItemPolicy, OrgConfig
from .timebound import When, active_at

# Higher wins when multiple orgs declare the same item with compatible stances.
_STANCE_PRECEDENCE = {
    "required": 5,
    "pinned": 4,
    "recommended": 3,
    "blocked": 2,
    "silent": 1,
}


@dataclass(frozen=True)
class EffectivePolicy:
    items: dict[str, tuple[str, ItemPolicy]]  # "type/name" -> (winning_org_id, policy)
    preferences: dict[str, object]
    prompts: dict[str, object]
    default_sources: dict[str, str]
    custom_sources: list[CustomSource]
    install_mode: Optional[str]
    held: tuple[str, ...]


def _time_filtered(cfg: OrgConfig, now: When) -> OrgConfig:
    """A copy of ``cfg`` with items outside their time window removed."""
    filtered = {
        item_type: {
            name: policy
            for name, policy in policies.items()
            if active_at(now, policy.required_after, policy.expires_at)
        }
        for item_type, policies in cfg.items.items()
    }
    return replace(cfg, items=filtered)


def _subject_status(paths: OrgPaths, orgs, configs: list[OrgConfig]) -> dict[str, tuple]:
    """Map each conflicting subject to its disposition.

    Values: ``("held",)`` | ``("honor", org_id)`` | ``("skip",)``. ``held``
    dominates when a subject has multiple conflicts in mixed states.

    ``configs`` are the (time-filtered) configs to detect conflicts over;
    ``orgs`` are the discovered entries, used only for resolution hashing.
    """
    org_hashes = {e.config.org_id: e.content_hash for e in orgs}
    conflicts = detect_conflicts(configs)
    resolutions = load_resolutions(paths)

    status: dict[str, tuple] = {}
    for conflict in conflicts:
        ih = input_hash_for((p.org_id for p in conflict.participants), org_hashes)
        res = resolutions.get(conflict.conflict_id)
        if res is not None and is_valid(res, ih) and res.decision != "defer":
            if res.decision.startswith("honor:"):
                disposition: tuple = ("honor", res.decision.split(":", 1)[1])
            elif res.decision == "skip":
                disposition = ("skip",)
            else:  # custom:<value> on a stance subject is unexpected — be safe
                disposition = ("held",)
        else:
            disposition = ("held",)

        prior = status.get(conflict.subject)
        if prior is None or disposition[0] == "held":
            status[conflict.subject] = disposition
    return status


def _pick(by_org: dict[str, ItemPolicy]) -> tuple[str, ItemPolicy]:
    # Deterministic: highest stance precedence, ties broken by lowest org_id.
    best_org = min(
        by_org,
        key=lambda oid: (-_STANCE_PRECEDENCE.get(by_org[oid].stance.value, 0), oid),
    )
    return best_org, by_org[best_org]


def _merge_scalar(
    by_org: dict[str, object], subject: str, status: dict[str, tuple], held: list[str]
):
    """Merge a single-valued subject. Returns (present, value)."""
    disp = status.get(subject)
    if disp is not None:
        if disp[0] == "held":
            held.append(subject)
            return False, None
        if disp[0] == "skip":
            return False, None
        if disp[0] == "honor":
            org = disp[1]
            if org in by_org:
                return True, by_org[org]
            return False, None
    # No conflict: all declared values agree (else it'd be a conflict).
    # Pick the lowest org_id deterministically.
    org = min(by_org)
    return True, by_org[org]


_EMPTY = EffectivePolicy({}, {}, {}, {}, [], None, ())


def effective_policy(paths: OrgPaths, now: Optional[When] = None) -> EffectivePolicy:
    if now is None:
        now = datetime.now(timezone.utc)
    orgs = discover_enrolled_orgs(paths)
    if not orgs:
        return _EMPTY
    configs = [_time_filtered(e.config, now) for e in orgs]
    return _assemble(paths, orgs, configs)


def effective_policy_for_repo(
    paths: OrgPaths,
    *,
    repo_path: Optional[str],
    git_remote: Optional[str],
    now: Optional[When] = None,
) -> EffectivePolicy:
    """Effective policy for a specific repo, with project overlays layered in.

    Each org's matching project profile is merged onto its own items/prompts
    before the cross-org merge, so P7 conflict handling keys on the same
    subjects whether they come from base policy or an overlay.
    """
    from .projects import match_project

    if now is None:
        now = datetime.now(timezone.utc)
    orgs = discover_enrolled_orgs(paths)
    if not orgs:
        return _EMPTY
    configs = []
    for e in orgs:
        cfg = e.config
        profile = match_project(cfg.projects, repo_path=repo_path, git_remote=git_remote)
        if profile is not None:
            merged_items = {
                item_type: {**cfg.items.get(item_type, {}), **profile.items.get(item_type, {})}
                for item_type in ITEM_TYPES
            }
            cfg = replace(
                cfg,
                items=merged_items,
                install_prompts={**cfg.install_prompts, **profile.prompts},
            )
        configs.append(_time_filtered(cfg, now))
    return _assemble(paths, orgs, configs)


def _assemble(paths: OrgPaths, orgs, configs: list[OrgConfig]) -> EffectivePolicy:
    status = _subject_status(paths, orgs, configs)
    held: list[str] = []

    # --- items -------------------------------------------------------------
    item_groups: dict[str, dict[str, ItemPolicy]] = {}
    for cfg in configs:
        for item_type in ITEM_TYPES:
            for name, policy in cfg.items.get(item_type, {}).items():
                item_groups.setdefault(f"{item_type}/{name}", {})[cfg.org_id] = policy

    items: dict[str, tuple[str, ItemPolicy]] = {}
    for subject, by_org in item_groups.items():
        disp = status.get(subject)
        if disp is not None:
            if disp[0] == "held":
                held.append(subject)
                continue
            if disp[0] == "skip":
                continue
            if disp[0] == "honor":
                org = disp[1]
                if org in by_org:
                    items[subject] = (org, by_org[org])
                continue
        items[subject] = _pick(by_org)

    # --- preferences -------------------------------------------------------
    preferences: dict[str, object] = {}
    pref_keys = {k for cfg in configs for k in cfg.install_preferences}
    for key in pref_keys:
        by_org = {
            cfg.org_id: cfg.install_preferences[key]
            for cfg in configs
            if key in cfg.install_preferences
        }
        present, value = _merge_scalar(by_org, f"preference.{key}", status, held)
        if present:
            preferences[key] = value

    # --- prompts (union; conflicts on prompt answers are out of scope) -----
    prompts: dict[str, object] = {}
    for cfg in configs:
        prompts.update(cfg.install_prompts)

    # --- default sources ---------------------------------------------------
    default_sources: dict[str, str] = {}
    for item_type in ITEM_TYPES:
        by_org = {
            cfg.org_id: cfg.default_sources[item_type]
            for cfg in configs
            if item_type in cfg.default_sources
        }
        if not by_org:
            continue
        present, value = _merge_scalar(
            by_org, f"sources.default.{item_type}", status, held
        )
        if present:
            default_sources[item_type] = value

    # --- install mode ------------------------------------------------------
    mode_by_org = {cfg.org_id: cfg.install_mode for cfg in configs if cfg.install_mode}
    install_mode: Optional[str] = None
    if mode_by_org:
        present, value = _merge_scalar(mode_by_org, "install.mode", status, held)
        if present:
            install_mode = value  # type: ignore[assignment]

    # --- custom sources (union by id; P6 guarantees no cross-org reach) -----
    custom_sources: list[CustomSource] = []
    seen_ids: set[str] = set()
    for cfg in configs:
        for cs in cfg.custom_sources:
            if cs.id not in seen_ids:
                seen_ids.add(cs.id)
                custom_sources.append(cs)

    return EffectivePolicy(
        items=items,
        preferences=preferences,
        prompts=prompts,
        default_sources=default_sources,
        custom_sources=custom_sources,
        install_mode=install_mode,
        held=tuple(sorted(set(held))),
    )
