"""Detecting org-config / trust changes between invocations.

Phase 2b seeds this module with dns_anchor key-rotation detection: fetch the
current well-known pubkey and compare its fingerprint to the pinned one. The
full change-propagation gate (re-hash on every invocation, diff, apply) builds
on these primitives in Phase 2e.
"""
from __future__ import annotations

from typing import Callable, Optional

PubkeyFetcher = Callable[[str], bytes]


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
