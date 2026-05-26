"""Org-config overlay engine.

Phase 1: schema, validation, single-org discovery, unsigned trust.
Phase 2: signed trust (pinned_key, dns_anchor), url delivery + refresh,
multi-org conflict detection/resolution, and per-invocation propagation.
"""
from .apply import ApplyOutcome, apply_org_policy
from .conflicts import Conflict, ConflictParticipant, detect_conflicts
from .crypto import OrgConfigCryptoUnavailable
from .discovery import EnrolledOrg, discover_enrolled_orgs
from .effective import EffectivePolicy, effective_policy
from .errors import (
    OrgConfigError,
    OrgConfigFetchError,
    OrgConfigMultiOrgRejectedError,
    OrgConfigParseError,
    OrgConfigTrustError,
    OrgConfigUnknownSchemaError,
    OrgConfigValidationError,
)
from .paths import OrgPaths
from .propagation import (
    GateResult,
    detect_changes,
    due_for_refresh,
    policy_diff,
    run_propagation_gate,
)
from .reconcile import OpenConflict, open_conflicts, scan_conflicts
from .resolutions import Resolution, load_resolutions, save_resolution
from .schema import CustomSource, ItemPolicy, OrgConfig, Stance

__all__ = [
    "ApplyOutcome",
    "Conflict",
    "ConflictParticipant",
    "CustomSource",
    "EffectivePolicy",
    "EnrolledOrg",
    "GateResult",
    "ItemPolicy",
    "OpenConflict",
    "OrgConfig",
    "OrgConfigCryptoUnavailable",
    "OrgConfigError",
    "OrgConfigFetchError",
    "OrgConfigMultiOrgRejectedError",
    "OrgConfigParseError",
    "OrgConfigTrustError",
    "OrgConfigUnknownSchemaError",
    "OrgConfigValidationError",
    "OrgPaths",
    "Resolution",
    "Stance",
    "apply_org_policy",
    "detect_changes",
    "detect_conflicts",
    "discover_enrolled_orgs",
    "due_for_refresh",
    "effective_policy",
    "load_resolutions",
    "open_conflicts",
    "policy_diff",
    "run_propagation_gate",
    "save_resolution",
    "scan_conflicts",
]
