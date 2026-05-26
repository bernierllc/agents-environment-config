"""Typed in-memory representation of a parsed, validated org config.

All fields are normalized: missing-but-optional becomes None or empty
collection; closed enums (Stance) replace strings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


SCHEMA_VERSION_SUPPORTED = frozenset({"1.0"})


RESERVED_SOURCE_IDS = frozenset({
    "aec.default.skills",
    "aec.default.rules",
    "aec.default.agents",
    "aec.default.mcps",
})


ITEM_TYPES = ("skills", "rules", "agents", "mcps")


DEFAULT_SOURCE_STANCES = ("keep", "replace", "deny")


class Stance(str, Enum):
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    BLOCKED = "blocked"
    PINNED = "pinned"
    SILENT = "silent"


@dataclass(frozen=True)
class ItemPolicy:
    source: str
    stance: Stance
    version: Optional[str] = None

    # Time-bounded rules (Phase 4b): ISO-8601 instants. The stance only takes
    # effect once ``required_after`` has passed and stops at ``expires_at``.
    required_after: Optional[str] = None
    expires_at: Optional[str] = None


@dataclass(frozen=True)
class CustomSource:
    id: str
    url: str
    ref: str
    contributes: tuple[str, ...]


@dataclass(frozen=True)
class ProjectMatch:
    """Selector for a per-project overlay (Phase 4a).

    At least one of ``git_remote`` / ``directory`` is set; both are globbed.
    """
    git_remote: Optional[str] = None
    directory: Optional[str] = None


@dataclass(frozen=True)
class ProjectProfile:
    """The policy delta a matching project overlay layers on the org policy.

    v1 carries ``items`` and ``prompts`` only; project-scoped preferences are
    deferred (the preference store is global, not repo-scoped).
    """
    items: dict[str, dict[str, "ItemPolicy"]]
    prompts: dict[str, Any]


@dataclass(frozen=True)
class ProjectOverlay:
    match: ProjectMatch
    profile: ProjectProfile


@dataclass(frozen=True)
class OrgConfig:
    schema_version: str
    org_id: str
    org_name: str
    config_version: str
    description: Optional[str]
    trust_mode: str  # Phase 1: only "unsigned"

    # sources block
    default_sources: dict[str, str]            # {"skills": "keep", ...}
    custom_sources: list[CustomSource]

    # items block
    items: dict[str, dict[str, ItemPolicy]]    # {"skills": {"name": ItemPolicy, ...}, ...}

    # install block (subset for Phase 1)
    install_preferences: dict[str, Any]
    install_prompts: dict[str, Any]
    install_agents_enabled: list[str]
    install_agents_disabled: list[str]
    install_mode: Optional[str] = None  # "managed" | "guided" | None

    # trust detail (Phase 2): plumbing for signed modes. Optional so unsigned
    # configs and existing callers are unaffected.
    trust_pubkey: Optional[str] = None
    trust_pubkey_url: Optional[str] = None
    trust_signature_url: Optional[str] = None
    trust_dns_domain: Optional[str] = None

    # refresh policy (Phase 2c): opt-in TTL for re-fetching url/mdm-sourced
    # configs on any invocation. None means "only on `aec update`".
    refresh_ttl_hours: Optional[int] = None
