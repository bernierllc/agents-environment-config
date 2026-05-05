"""Org-config overlay engine.

Phase 1: schema, validation, single-org discovery, unsigned trust.
"""
from .discovery import EnrolledOrg, discover_enrolled_orgs
from .errors import (
    OrgConfigError,
    OrgConfigMultiOrgRejectedError,
    OrgConfigParseError,
    OrgConfigTrustError,
    OrgConfigUnknownSchemaError,
    OrgConfigValidationError,
)
from .paths import OrgPaths
from .schema import CustomSource, ItemPolicy, OrgConfig, Stance

__all__ = [
    "CustomSource",
    "EnrolledOrg",
    "ItemPolicy",
    "OrgConfig",
    "OrgConfigError",
    "OrgConfigMultiOrgRejectedError",
    "OrgConfigParseError",
    "OrgConfigTrustError",
    "OrgConfigUnknownSchemaError",
    "OrgConfigValidationError",
    "OrgPaths",
    "Stance",
    "discover_enrolled_orgs",
]
