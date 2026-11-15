"""Error hierarchy for org-config loading.

Distinct subclasses so the CLI can map each to a specific exit code
(10=trust, 12=multi-org-rejected, 13=schema/validation).
"""
from __future__ import annotations

from typing import Optional


class OrgConfigError(Exception):
    """Base for all org-config errors."""


class OrgApplyCommittedError(OrgConfigError):
    """An apply failed AFTER its commit point (sources published, approval stamped).

    The committed state stays; callers must never restore over it. The stamp left an
    ``apply_failed`` marker, so the next ``aec org apply`` retries what is missing.
    """


class OrgConfigParseError(OrgConfigError):
    """YAML or frontmatter could not be parsed."""


class OrgConfigValidationError(OrgConfigError):
    """Parsed dict failed schema validation."""

    def __init__(self, message: str, field_path: Optional[str] = None) -> None:
        self.field_path = field_path
        if field_path:
            super().__init__(f"{field_path}: {message}")
        else:
            super().__init__(message)


class OrgConfigUnknownSchemaError(OrgConfigError):
    """schema_version is unknown to this build of aec."""


class OrgConfigTrustError(OrgConfigError):
    """Trust verification refused the config (or user declined unsigned warning)."""


class OrgConfigMultiOrgRejectedError(OrgConfigError):
    """Phase 1: more than one org config present in ~/.aec/orgs/."""


class OrgConfigFetchError(OrgConfigError):
    """A remote fetch (config or pubkey) failed or was refused."""
