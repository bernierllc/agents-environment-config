"""Org-config overlay engine.

Phase 1: schema, validation, single-org discovery, unsigned trust.
Phase 2: signed trust (pinned_key, dns_anchor), url delivery + refresh,
multi-org conflict detection/resolution, and per-invocation propagation.
Phase 4: per-project overlays, time-bounded rules, declarative enrollment_script
with custom-source cloning, and branding.
"""
from .apply import ApplyOutcome, apply_org_policy
from .conflicts import Conflict, ConflictParticipant, detect_conflicts
from .crypto import OrgConfigCryptoUnavailable
from .discovery import EnrolledOrg, discover_enrolled_orgs
from .effective import EffectivePolicy, effective_policy, effective_policy_for_repo
from .enrollment import EnrollmentResult, StepResult, run_enrollment_script
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
from .projects import match_project, normalize_git_remote
from .propagation import (
    GateResult,
    detect_changes,
    due_for_refresh,
    policy_diff,
    run_propagation_gate,
)
from .reconcile import OpenConflict, open_conflicts, scan_conflicts
from .resolutions import Resolution, load_resolutions, save_resolution
from .schema import (
    Branding,
    CustomSource,
    ItemPolicy,
    OrgConfig,
    ProjectMatch,
    ProjectOverlay,
    ProjectProfile,
    Stance,
)
from .sources_sync import SyncResult, sync_source, sync_sources
from .timebound import active_at

__all__ = [
    "ApplyOutcome",
    "Branding",
    "Conflict",
    "ConflictParticipant",
    "CustomSource",
    "EffectivePolicy",
    "EnrolledOrg",
    "EnrollmentResult",
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
    "ProjectMatch",
    "ProjectOverlay",
    "ProjectProfile",
    "Resolution",
    "Stance",
    "StepResult",
    "SyncResult",
    "active_at",
    "apply_org_policy",
    "detect_changes",
    "detect_conflicts",
    "discover_enrolled_orgs",
    "due_for_refresh",
    "effective_policy",
    "effective_policy_for_repo",
    "load_resolutions",
    "match_project",
    "normalize_git_remote",
    "open_conflicts",
    "policy_diff",
    "run_enrollment_script",
    "run_propagation_gate",
    "save_resolution",
    "scan_conflicts",
    "sync_source",
    "sync_sources",
]
