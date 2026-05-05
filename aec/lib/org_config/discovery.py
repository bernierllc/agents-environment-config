"""Locate and load enrolled org configs from ``~/.aec/orgs/``.

Phase 1 supports exactly zero or one enrolled org. If a second config
file is present we refuse to proceed rather than silently picking one —
multi-org behavior is intentionally deferred to Phase 3 where the
conflict-resolution model is properly designed.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import OrgConfigMultiOrgRejectedError
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

    yaml_files = sorted(paths.orgs_dir.glob("*.yaml"))
    if not yaml_files:
        return []

    if len(yaml_files) > 1:
        names = ", ".join(p.name for p in yaml_files)
        raise OrgConfigMultiOrgRejectedError(
            f"phase 1 supports a single enrolled org; found {len(yaml_files)} "
            f"({names}). Multi-org support arrives in phase 3."
        )

    source_path = yaml_files[0]
    raw_bytes = source_path.read_bytes()
    frontmatter, body = parse_org_config_text(raw_bytes.decode("utf-8"))
    config = validate_org_config(frontmatter, body)
    return [
        EnrolledOrg(
            config=config,
            content_hash=hash_config_bytes(raw_bytes),
            source_path=source_path,
            raw_bytes=raw_bytes,
        )
    ]
