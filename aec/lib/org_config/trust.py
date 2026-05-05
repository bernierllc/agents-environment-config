"""Trust verification for org configs.

Phase 1 only supports ``trust_mode: unsigned`` and requires the caller
to provide explicit consent (typically gathered through an interactive
warning prompt or the ``--allow-unsigned`` flag). The signed modes
(``pinned_key``, ``dns_anchor``) are reserved for Phase 2 and are
rejected with a clear "phase 2" error message so users see a deliberate
deferral rather than a generic validation failure.

The ``verify_trust`` signature returns a result object so Phase 2 can
extend it (pubkey fingerprint, signature timestamp, etc.) without
breaking callers.
"""
from __future__ import annotations

from dataclasses import dataclass

from .errors import OrgConfigTrustError


@dataclass(frozen=True)
class UnsignedConsent:
    acknowledged: bool


@dataclass(frozen=True)
class TrustResult:
    trust_mode: str
    acknowledged: bool


class UnsignedConsentDeclined(OrgConfigTrustError):
    """Caller refused to acknowledge the unsigned-config warning."""


_PHASE_2_MODES = frozenset({"pinned_key", "dns_anchor"})


def verify_trust(
    *,
    trust_mode: str,
    config_bytes: bytes,
    consent: UnsignedConsent,
) -> TrustResult:
    if trust_mode in _PHASE_2_MODES:
        raise OrgConfigTrustError(
            f"trust_mode '{trust_mode}' requires signed-config support, "
            "which arrives in phase 2"
        )
    if trust_mode != "unsigned":
        raise OrgConfigTrustError(f"unknown trust_mode: '{trust_mode}'")
    if not consent.acknowledged:
        raise UnsignedConsentDeclined(
            "unsigned org configs require explicit consent; pass "
            "--allow-unsigned or accept the warning prompt"
        )
    return TrustResult(trust_mode="unsigned", acknowledged=True)
