"""Detecting org-config / trust changes between invocations.

Phase 2b seeds this module with dns_anchor key-rotation detection: fetch the
current well-known pubkey and compare its fingerprint to the pinned one. The
full change-propagation gate (re-hash on every invocation, diff, apply) builds
on these primitives in Phase 2e.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional, Union

from .schema import ITEM_TYPES, OrgConfig

PubkeyFetcher = Callable[[str], bytes]


@dataclass(frozen=True)
class OrgChange:
    org_id: str
    status: str  # "new" | "changed" | "unchanged"
    old_hash: Optional[str]
    new_hash: str


def detect_changes(paths, *, now: Optional[str] = None) -> list[OrgChange]:
    """Compare each enrolled org's on-disk hash to its recorded state hash."""
    from .discovery import discover_enrolled_orgs
    from .state import read_state

    changes: list[OrgChange] = []
    for enrolled in discover_enrolled_orgs(paths):
        org_id = enrolled.config.org_id
        new_hash = enrolled.content_hash
        st = read_state(paths, org_id)
        if st is None:
            changes.append(OrgChange(org_id, "new", None, new_hash))
        elif st.config_hash != new_hash:
            changes.append(OrgChange(org_id, "changed", st.config_hash, new_hash))
        else:
            changes.append(OrgChange(org_id, "unchanged", st.config_hash, new_hash))
    return changes


@dataclass(frozen=True)
class PolicyDiff:
    items_added: tuple[str, ...]
    items_removed: tuple[str, ...]
    items_changed: tuple[str, ...]
    source_changes: tuple[str, ...]
    preference_changes: tuple[str, ...]
    trust_mode_change: Optional[str]
    install_mode_change: Optional[str]

    def is_empty(self) -> bool:
        return not (
            self.items_added
            or self.items_removed
            or self.items_changed
            or self.source_changes
            or self.preference_changes
            or self.trust_mode_change
            or self.install_mode_change
        )


def policy_diff(old: OrgConfig, new: OrgConfig) -> PolicyDiff:
    """Render-ready diff of two versions of the same org's policy."""
    old_items = _flatten_items(old)
    new_items = _flatten_items(new)

    added = sorted(k for k in new_items if k not in old_items)
    removed = sorted(k for k in old_items if k not in new_items)
    changed = sorted(
        k for k in old_items if k in new_items and old_items[k] != new_items[k]
    )

    source_changes = []
    for item_type in ITEM_TYPES:
        o = old.default_sources.get(item_type)
        n = new.default_sources.get(item_type)
        if o != n:
            source_changes.append(f"{item_type}: {o}->{n}")

    pref_changes = []
    for key in sorted(set(old.install_preferences) | set(new.install_preferences)):
        o = old.install_preferences.get(key)
        n = new.install_preferences.get(key)
        if o != n:
            pref_changes.append(f"{key}: {o}->{n}")

    trust_change = (
        f"{old.trust_mode}->{new.trust_mode}" if old.trust_mode != new.trust_mode else None
    )
    install_change = (
        f"{old.install_mode}->{new.install_mode}"
        if old.install_mode != new.install_mode
        else None
    )

    return PolicyDiff(
        items_added=tuple(added),
        items_removed=tuple(removed),
        items_changed=tuple(changed),
        source_changes=tuple(source_changes),
        preference_changes=tuple(pref_changes),
        trust_mode_change=trust_change,
        install_mode_change=install_change,
    )


def _flatten_items(cfg: OrgConfig) -> dict[str, tuple]:
    flat: dict[str, tuple] = {}
    for item_type in ITEM_TYPES:
        for name, policy in cfg.items.get(item_type, {}).items():
            flat[f"{item_type}/{name}"] = (policy.source, policy.stance.value, policy.version)
    return flat


def _parse_dt(value: Union[str, datetime]) -> datetime:
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def due_for_refresh(
    *,
    last_verified_at: Union[str, datetime],
    ttl_hours: Optional[int],
    now: Union[str, datetime],
) -> bool:
    """Whether a url/mdm-sourced config is due for a TTL-based auto-refetch.

    ``ttl_hours`` of None (the default) means "never auto-refetch" — only an
    explicit ``aec update`` re-fetches. Used by the Phase 2e propagation gate.
    """
    if not ttl_hours:
        return False
    elapsed = _parse_dt(now) - _parse_dt(last_verified_at)
    return elapsed.total_seconds() >= ttl_hours * 3600


def detect_dns_rotation(
    *,
    dns_domain: str,
    pinned_fingerprint: Optional[str],
    fetcher: PubkeyFetcher,
    now: str,
) -> Optional[dict]:
    """Return a ``key_rotation_pending`` payload if the domain's published key
    no longer matches the pinned fingerprint, else ``None``.

    Detection only needs the public key, not the signature: a fingerprint
    mismatch is sufficient to flag a rotation for the operator to acknowledge.
    """
    from .crypto import decode_pubkey, fingerprint
    from .trust import WELL_KNOWN_PUBKEY_PATH

    if not pinned_fingerprint:
        return None

    url = f"https://{dns_domain}{WELL_KNOWN_PUBKEY_PATH}"
    fetched = fetcher(url)
    pubkey_b64 = fetched.decode("utf-8").strip() if isinstance(fetched, bytes) else fetched.strip()
    current_fp = fingerprint(decode_pubkey(pubkey_b64))

    if current_fp == pinned_fingerprint:
        return None
    return {
        "detected_at": now,
        "new_fingerprint": current_fp,
        "old_fingerprint": pinned_fingerprint,
    }
