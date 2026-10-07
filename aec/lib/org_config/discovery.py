"""Locate and load enrolled org configs from ``~/.aec/orgs/``.

Multiple orgs may be enrolled simultaneously (Phase 2d). Results are sorted
deterministically by ``org_id`` so conflict detection and display are stable
across runs. A config that fails to parse/validate still raises — a broken
org config must surface, not be silently dropped.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .hashing import hash_config_bytes
from .parser import parse_org_config_text
from .paths import OrgPaths
from .schema import OrgConfig
from .validator import validate_org_config


@dataclass(frozen=True)
class EnrolledOrg:
    config: OrgConfig
    content_hash: str
    source_path: Path
    raw_bytes: bytes


def discover_enrolled_orgs(paths: OrgPaths) -> list[EnrolledOrg]:
    if not paths.orgs_dir.exists():
        return []

    enrolled: list[EnrolledOrg] = []
    for source_path in sorted(paths.orgs_dir.glob("*.yaml")):
        raw_bytes = source_path.read_bytes()
        frontmatter, body = parse_org_config_text(raw_bytes.decode("utf-8"))
        config = validate_org_config(frontmatter, body)
        enrolled.append(
            EnrolledOrg(
                config=config,
                content_hash=hash_config_bytes(raw_bytes),
                source_path=source_path,
                raw_bytes=raw_bytes,
            )
        )

    enrolled.sort(key=lambda e: e.config.org_id)
    return enrolled


def migrate_state(paths: OrgPaths, org_id: str):
    """Backfill ``trust_dns_domain`` for a dns_anchor state enrolled before it existed.

    A missing domain is never compared as None and never means "accept
    anything". URL-sourced state can't prove the on-disk domain was chosen by a
    person (refresh used to rewrite config and hash together), so it becomes a
    ``trust_change``. Local state backfills only when the on-disk config still
    hashes to ``config_hash``. The result is persisted before the caller does
    any network IO. Returns the (possibly updated) state, or None.
    """
    import dataclasses

    from .errors import OrgConfigError
    from .state import read_state, write_state

    state = read_state(paths, org_id)
    if state is None or state.trust_mode != "dns_anchor" or state.trust_dns_domain:
        return state
    if state.pending and state.pending.get("kind") == "trust_change":
        return state

    cfg_path = paths.config_for(org_id)
    raw = cfg_path.read_bytes() if cfg_path.exists() else None
    on_disk_domain = None
    if raw is not None:
        try:
            frontmatter, body = parse_org_config_text(raw.decode("utf-8"))
            on_disk_domain = validate_org_config(frontmatter, body).trust_dns_domain
        except (OrgConfigError, UnicodeDecodeError):
            on_disk_domain = None

    if (
        state.source_of_record == "local"
        and raw is not None
        and on_disk_domain
        and hash_config_bytes(raw) == state.config_hash
    ):
        state = dataclasses.replace(state, trust_dns_domain=on_disk_domain)
    else:
        state = dataclasses.replace(
            state,
            pending={
                "kind": "trust_change",
                "from": {"trust_dns_domain": None},
                "to": {"trust_dns_domain": on_disk_domain},
            },
        )
    write_state(paths, state)
    return state
