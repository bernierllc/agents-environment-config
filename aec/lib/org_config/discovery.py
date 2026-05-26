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
