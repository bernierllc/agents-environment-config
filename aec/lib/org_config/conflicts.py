"""Cross-org conflict detection.

Pure functions over loaded :class:`OrgConfig` objects — no IO. When two or more
enrolled orgs disagree on the same subject, AEC never picks a winner (principle
P2); it surfaces a :class:`Conflict` for the user to resolve.

Detected kinds (design spec "Conflict types detected"):

  * ``stance``             — one org wants an item installed, another blocks it
  * ``version``            — install-intent orgs declare differing version pins
  * ``source_replacement`` — orgs disagree on a default source's stance
  * ``preference``         — orgs set the same install preference to different values
  * ``install_mode``       — orgs disagree on managed vs guided

P6 violations (an org declaring policy on another org's source) are a parse
error enforced in the validator, not a conflict, so they never reach here.
``project_rule`` conflicts await the Phase 4 ``projects`` block.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable

from .schema import ITEM_TYPES, OrgConfig

_INSTALL_INTENTS = {"required", "recommended", "pinned"}
_BLOCK_INTENTS = {"blocked"}


@dataclass(frozen=True)
class ConflictParticipant:
    org_id: str
    value: str


@dataclass(frozen=True)
class Conflict:
    conflict_id: str
    kind: str
    subject: str
    participants: tuple[ConflictParticipant, ...]


def _conflict_id(kind: str, subject: str, org_ids: Iterable[str]) -> str:
    key = f"{kind}|{subject}|{','.join(sorted(org_ids))}"
    return "conf-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


def _make(kind: str, subject: str, items: dict[str, str]) -> Conflict:
    participants = tuple(
        ConflictParticipant(org_id=oid, value=val) for oid, val in sorted(items.items())
    )
    return Conflict(
        conflict_id=_conflict_id(kind, subject, items.keys()),
        kind=kind,
        subject=subject,
        participants=participants,
    )


def detect_conflicts(configs: list[OrgConfig]) -> list[Conflict]:
    """Return every conflict across ``configs``, ordered by conflict_id."""
    conflicts: list[Conflict] = []
    conflicts.extend(_item_conflicts(configs))
    conflicts.extend(_source_replacement_conflicts(configs))
    conflicts.extend(_preference_conflicts(configs))
    conflicts.extend(_install_mode_conflicts(configs))
    conflicts.sort(key=lambda c: c.conflict_id)
    return conflicts


def _item_conflicts(configs: list[OrgConfig]) -> list[Conflict]:
    # Group every declared item policy by (type, name, source) across all orgs.
    groups: dict[tuple[str, str, str], dict[str, object]] = {}
    for cfg in configs:
        for item_type in ITEM_TYPES:
            for name, policy in cfg.items.get(item_type, {}).items():
                key = (item_type, name, policy.source)
                groups.setdefault(key, {})[cfg.org_id] = policy

    out: list[Conflict] = []
    for (item_type, name, _source), by_org in groups.items():
        if len(by_org) < 2:
            continue
        subject = f"{item_type}/{name}"

        stances = {oid: p.stance.value for oid, p in by_org.items() if p.stance.value != "silent"}
        has_install = any(s in _INSTALL_INTENTS for s in stances.values())
        has_block = any(s in _BLOCK_INTENTS for s in stances.values())
        if has_install and has_block:
            out.append(_make("stance", subject, stances))

        versions = {
            oid: p.version
            for oid, p in by_org.items()
            if p.stance.value in _INSTALL_INTENTS and p.version is not None
        }
        if len(set(versions.values())) > 1:
            out.append(_make("version", subject, versions))
    return out


def _source_replacement_conflicts(configs: list[OrgConfig]) -> list[Conflict]:
    out: list[Conflict] = []
    for item_type in ITEM_TYPES:
        by_org = {
            cfg.org_id: cfg.default_sources[item_type]
            for cfg in configs
            if item_type in cfg.default_sources
        }
        if len(set(by_org.values())) > 1:
            out.append(_make("source_replacement", f"sources.default.{item_type}", by_org))
    return out


def _preference_conflicts(configs: list[OrgConfig]) -> list[Conflict]:
    keys: set[str] = set()
    for cfg in configs:
        keys.update(cfg.install_preferences.keys())

    out: list[Conflict] = []
    for key in keys:
        by_org = {
            cfg.org_id: str(cfg.install_preferences[key])
            for cfg in configs
            if key in cfg.install_preferences
        }
        if len(set(by_org.values())) > 1:
            out.append(_make("preference", f"preference.{key}", by_org))
    return out


def _install_mode_conflicts(configs: list[OrgConfig]) -> list[Conflict]:
    by_org = {cfg.org_id: cfg.install_mode for cfg in configs if cfg.install_mode is not None}
    if len(set(by_org.values())) > 1:
        return [_make("install_mode", "install.mode", by_org)]
    return []
