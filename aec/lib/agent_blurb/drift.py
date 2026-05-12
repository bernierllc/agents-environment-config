"""Drift detection between shipped template, stored config, and on-disk content.

See docs/superpowers/specs/2026-05-12-aec-agent-blurb-design.md §6.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from aec.lib.agent_blurb.markers import find_block
from aec.lib.agent_blurb.render import extract_inner_body, sha256_short


class DriftState(str, Enum):
    CLEAN = "clean"
    NOT_INSTALLED = "not_installed"
    UPSTREAM_UPDATE = "upstream_update"
    MANUAL_EDIT = "manual_edit"
    CONFLICT = "conflict"


def compute_drift(
    on_disk_content: str,
    stored_template_hash: Optional[str],
    stored_content_hash: Optional[str],
    shipped_template_hash: str,
) -> DriftState:
    """Compute drift state from the three signals.

    The on-disk content hash is recomputed by re-hashing the body between
    markers — the marker's claimed content-hash is informational only and
    cannot be trusted as a signal of body integrity.
    """
    try:
        loc = find_block(on_disk_content)
    except Exception:
        return DriftState.CONFLICT  # malformed -> treat as conflict
    if loc is None or stored_template_hash is None or stored_content_hash is None:
        return DriftState.NOT_INSTALLED

    block = on_disk_content[loc.start:loc.end]
    try:
        on_disk_content_hash = sha256_short(extract_inner_body(block))
    except ValueError:
        return DriftState.CONFLICT

    template_changed = shipped_template_hash != stored_template_hash
    edited_on_disk = on_disk_content_hash != stored_content_hash

    if not template_changed and not edited_on_disk:
        return DriftState.CLEAN
    if template_changed and not edited_on_disk:
        return DriftState.UPSTREAM_UPDATE
    if not template_changed and edited_on_disk:
        return DriftState.MANUAL_EDIT
    return DriftState.CONFLICT
