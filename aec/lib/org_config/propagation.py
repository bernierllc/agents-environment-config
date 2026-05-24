"""Detecting org-config / trust changes between invocations.

Phase 2b seeds this module with dns_anchor key-rotation detection: fetch the
current well-known pubkey and compare its fingerprint to the pinned one. The
full change-propagation gate (re-hash on every invocation, diff, apply) builds
on these primitives in Phase 2e.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional, Union

PubkeyFetcher = Callable[[str], bytes]


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
