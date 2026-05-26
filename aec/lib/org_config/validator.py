"""Schema validator for org-config overlays (Phase 1)."""
from __future__ import annotations

from typing import Any

from .allow_lists import (
    PREFERENCES_ALLOW_LIST,
    PREFERENCES_DYNAMIC_NAMESPACES,
    PROMPTS_ALLOW_LIST,
    PROMPTS_DYNAMIC_PREFIXES,
)
from .errors import OrgConfigUnknownSchemaError, OrgConfigValidationError
from .timebound import parse_iso
from .schema import (
    ITEM_TYPES,
    RESERVED_SOURCE_IDS,
    SCHEMA_VERSION_SUPPORTED,
    CustomSource,
    ItemPolicy,
    OrgConfig,
    Stance,
)


_STANCE_VALUES = {s.value for s in Stance}


def _require(d: dict, key: str, field_path: str) -> Any:
    if key not in d or d[key] is None:
        raise OrgConfigValidationError(f"{key} is required", field_path=field_path)
    return d[key]


def _validate_iso(value: Any, field_path: str):
    if value is None:
        return None
    try:
        parse_iso(str(value))
    except ValueError:
        raise OrgConfigValidationError(
            f"{field_path.rsplit('.', 1)[-1]} must be an ISO-8601 date/time",
            field_path=field_path,
        )
    return value


def validate_org_config(frontmatter: dict, body: dict) -> OrgConfig:
    schema_version = frontmatter.get("schema_version")
    if schema_version not in SCHEMA_VERSION_SUPPORTED:
        raise OrgConfigUnknownSchemaError(
            f"unsupported schema_version: {schema_version}"
        )

    org_id = _require(frontmatter, "org_id", "org_id")
    org_name = _require(frontmatter, "org_name", "org_name")
    config_version = _require(frontmatter, "config_version", "config_version")
    description = frontmatter.get("description")

    trust = frontmatter.get("trust") or {}
    trust_mode = trust.get("mode")
    if trust_mode is None:
        raise OrgConfigValidationError("trust.mode is required", field_path="trust.mode")
    if trust_mode not in ("unsigned", "pinned_key", "dns_anchor"):
        raise OrgConfigValidationError(
            f"unknown trust.mode: {trust_mode!r}", field_path="trust.mode"
        )
    trust_pubkey = trust.get("pubkey")
    trust_pubkey_url = trust.get("pubkey_url")
    trust_signature_url = trust.get("signature_url")
    trust_dns_domain = trust.get("dns_domain")
    if trust_mode == "pinned_key" and not (trust_pubkey or trust_pubkey_url):
        raise OrgConfigValidationError(
            "pinned_key trust requires 'pubkey' or 'pubkey_url'", field_path="trust.pubkey"
        )
    if trust_mode == "dns_anchor" and not trust_dns_domain:
        raise OrgConfigValidationError(
            "dns_anchor trust requires 'dns_domain'", field_path="trust.dns_domain"
        )
    for url_field, url_value in (
        ("trust.pubkey_url", trust_pubkey_url),
        ("trust.signature_url", trust_signature_url),
    ):
        if url_value is not None and not str(url_value).startswith("https://"):
            raise OrgConfigValidationError(
                f"{url_field} must be an https:// URL", field_path=url_field
            )

    refresh_block = body.get("refresh") or {}
    refresh_ttl_hours = refresh_block.get("ttl_hours")
    if refresh_ttl_hours is not None:
        if not isinstance(refresh_ttl_hours, int) or isinstance(refresh_ttl_hours, bool) or refresh_ttl_hours <= 0:
            raise OrgConfigValidationError(
                "ttl_hours must be a positive integer", field_path="refresh.ttl_hours"
            )

    if body.get("projects"):
        raise OrgConfigValidationError(
            "projects block is a Phase 4 feature, not supported in Phase 1",
            field_path="projects",
        )
    install_block = body.get("install") or {}
    if install_block.get("enrollment_script"):
        raise OrgConfigValidationError(
            "enrollment_script is a Phase 2+ feature, not supported in Phase 1",
            field_path="install.enrollment_script",
        )

    sources_block = body.get("sources") or {}
    default_sources = dict(sources_block.get("default") or {})

    custom_sources_raw = sources_block.get("custom") or []
    custom_sources: list[CustomSource] = []
    for s in custom_sources_raw:
        custom_sources.append(
            CustomSource(
                id=s["id"],
                url=s["url"],
                ref=s["ref"],
                contributes=tuple(s["contributes"]),
            )
        )

    valid_source_ids = set(RESERVED_SOURCE_IDS) | {cs.id for cs in custom_sources}

    items_block = body.get("items") or {}
    items: dict[str, dict[str, ItemPolicy]] = {}
    for type_name in ITEM_TYPES:
        type_items = items_block.get(type_name) or {}
        validated: dict[str, ItemPolicy] = {}
        for item_name, policy_dict in type_items.items():
            base_path = f"items.{type_name}.{item_name}"
            if not isinstance(policy_dict, dict):
                raise OrgConfigValidationError(
                    "item policy must be a mapping", field_path=base_path
                )
            source = policy_dict.get("source")
            if source is None:
                raise OrgConfigValidationError(
                    "source field is required",
                    field_path=f"{base_path}.source",
                )
            if source not in valid_source_ids:
                raise OrgConfigValidationError(
                    f"unknown source '{source}' (not declared in sources.custom and not reserved)",
                    field_path=f"{base_path}.source",
                )
            stance_raw = policy_dict.get("stance")
            if stance_raw not in _STANCE_VALUES:
                raise OrgConfigValidationError(
                    f"unknown stance: {stance_raw!r}",
                    field_path=f"{base_path}.stance",
                )
            version = policy_dict.get("version")
            required_after = _validate_iso(
                policy_dict.get("required_after"), f"{base_path}.required_after"
            )
            expires_at = _validate_iso(
                policy_dict.get("expires_at"), f"{base_path}.expires_at"
            )
            if (
                required_after is not None
                and expires_at is not None
                and parse_iso(expires_at) <= parse_iso(required_after)
            ):
                raise OrgConfigValidationError(
                    "expires_at must be after required_after",
                    field_path=f"{base_path}.expires_at",
                )
            validated[item_name] = ItemPolicy(
                source=source,
                stance=Stance(stance_raw),
                version=version,
                required_after=required_after,
                expires_at=expires_at,
            )
        items[type_name] = validated

    install_preferences = dict((install_block.get("preferences") or {}))
    for k in install_preferences:
        if k in PREFERENCES_ALLOW_LIST:
            continue
        if any(k.startswith(f"{ns}.") for ns in PREFERENCES_DYNAMIC_NAMESPACES):
            continue
        raise OrgConfigValidationError(
            f"key '{k}' is not allow-listed",
            field_path=f"install.preferences.{k}",
        )

    install_prompts = dict((install_block.get("prompts") or {}))
    for k in install_prompts:
        if k in PROMPTS_ALLOW_LIST:
            continue
        if any(k.startswith(f"{prefix}.") for prefix in PROMPTS_DYNAMIC_PREFIXES):
            continue
        raise OrgConfigValidationError(
            f"key '{k}' is not allow-listed",
            field_path=f"install.prompts.{k}",
        )

    install_agents = install_block.get("agents") or {}
    install_agents_enabled = list(install_agents.get("enabled") or [])
    install_agents_disabled = list(install_agents.get("disabled") or [])

    install_mode = install_block.get("mode")
    if install_mode is not None and install_mode not in ("managed", "guided"):
        raise OrgConfigValidationError(
            f"unknown install.mode: {install_mode!r} (expected 'managed' or 'guided')",
            field_path="install.mode",
        )

    return OrgConfig(
        schema_version=schema_version,
        org_id=org_id,
        org_name=org_name,
        config_version=config_version,
        description=description,
        trust_mode=trust_mode,
        default_sources=default_sources,
        custom_sources=custom_sources,
        items=items,
        install_preferences=install_preferences,
        install_prompts=install_prompts,
        install_agents_enabled=install_agents_enabled,
        install_agents_disabled=install_agents_disabled,
        install_mode=install_mode,
        trust_pubkey=trust_pubkey,
        trust_pubkey_url=trust_pubkey_url,
        trust_signature_url=trust_signature_url,
        trust_dns_domain=trust_dns_domain,
        refresh_ttl_hours=refresh_ttl_hours,
    )
