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


@dataclass(frozen=True)
class CustomSource:
    id: str
    url: str
    ref: str
    contributes: tuple[str, ...]


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

    # trust detail (Phase 2): plumbing for signed modes. Optional so unsigned
    # configs and existing callers are unaffected.
    trust_pubkey: Optional[str] = None
    trust_pubkey_url: Optional[str] = None
    trust_signature_url: Optional[str] = None
    trust_dns_domain: Optional[str] = None

    # refresh policy (Phase 2c): opt-in TTL for re-fetching url/mdm-sourced
    # configs on any invocation. None means "only on `aec update`".
    refresh_ttl_hours: Optional[int] = None
