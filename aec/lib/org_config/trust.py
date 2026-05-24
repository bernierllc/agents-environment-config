"""Trust verification for org configs.

Supported modes:

- ``unsigned`` — requires explicit caller consent (``--allow-unsigned`` or an
  interactive acknowledgment). No cryptographic guarantee.
- ``pinned_key`` (Phase 2a) — verifies a detached ed25519 signature over the
  config bytes against an inline public key, with TOFU fingerprint pinning. A
  changed key halts until acknowledged via ``aec org trust-rotate``.
- ``dns_anchor`` — domain-anchored pubkey discovery: the public key is fetched
  over https from ``https://<dns_domain>/.well-known/aec-pubkey`` and used to
  verify a detached signature, with the same TOFU fingerprint pinning as
  ``pinned_key``.

``verify_trust`` returns a result object carrying the verified pubkey
fingerprint so callers can pin / re-verify it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .errors import OrgConfigTrustError

PubkeyFetcher = Callable[[str], bytes]

WELL_KNOWN_PUBKEY_PATH = "/.well-known/aec-pubkey"


@dataclass(frozen=True)
class UnsignedConsent:
    acknowledged: bool


@dataclass(frozen=True)
class TrustResult:
    trust_mode: str
    acknowledged: bool
    pubkey_fingerprint: Optional[str] = None


class UnsignedConsentDeclined(OrgConfigTrustError):
    """Caller refused to acknowledge the unsigned-config warning."""


def verify_trust(
    *,
    trust_mode: str,
    config_bytes: bytes,
    consent: UnsignedConsent,
    pubkey_b64: Optional[str] = None,
    signature: Optional[bytes] = None,
    pinned_fingerprint: Optional[str] = None,
    dns_domain: Optional[str] = None,
    pubkey_fetcher: Optional[PubkeyFetcher] = None,
) -> TrustResult:
    if trust_mode == "unsigned":
        if not consent.acknowledged:
            raise UnsignedConsentDeclined(
                "unsigned org configs require explicit consent; pass "
                "--allow-unsigned or accept the warning prompt"
            )
        return TrustResult(trust_mode="unsigned", acknowledged=True)
    if trust_mode == "pinned_key":
        return _verify_pinned_key(config_bytes, pubkey_b64, signature, pinned_fingerprint)
    if trust_mode == "dns_anchor":
        return _verify_dns_anchor(
            config_bytes, dns_domain, signature, pinned_fingerprint, pubkey_fetcher
        )
    raise OrgConfigTrustError(f"unknown trust_mode: '{trust_mode}'")


def _verify_pinned_key(
    config_bytes: bytes,
    pubkey_b64: Optional[str],
    signature: Optional[bytes],
    pinned_fingerprint: Optional[str],
) -> TrustResult:
    if not pubkey_b64:
        raise OrgConfigTrustError(
            "pinned_key trust requires an inline 'pubkey' (pubkey_url fetch arrives in phase 2c)"
        )
    if signature is None:
        raise OrgConfigTrustError(
            "pinned_key trust requires a detached signature (provide <config>.sig or --signature)"
        )
    return _verify_with_pubkey(
        config_bytes, pubkey_b64, signature, pinned_fingerprint, trust_mode="pinned_key"
    )


def _verify_dns_anchor(
    config_bytes: bytes,
    dns_domain: Optional[str],
    signature: Optional[bytes],
    pinned_fingerprint: Optional[str],
    pubkey_fetcher: Optional[PubkeyFetcher],
) -> TrustResult:
    if not dns_domain:
        raise OrgConfigTrustError("dns_anchor trust requires 'trust.dns_domain'")
    if signature is None:
        raise OrgConfigTrustError(
            "dns_anchor trust requires a detached signature (provide <config>.sig or --signature)"
        )
    if pubkey_fetcher is None:
        from .fetch import fetch_bytes

        pubkey_fetcher = fetch_bytes

    url = f"https://{dns_domain}{WELL_KNOWN_PUBKEY_PATH}"
    fetched = pubkey_fetcher(url)
    pubkey_b64 = fetched.decode("utf-8").strip() if isinstance(fetched, bytes) else fetched.strip()
    return _verify_with_pubkey(
        config_bytes, pubkey_b64, signature, pinned_fingerprint, trust_mode="dns_anchor"
    )


def _verify_with_pubkey(
    config_bytes: bytes,
    pubkey_b64: str,
    signature: bytes,
    pinned_fingerprint: Optional[str],
    *,
    trust_mode: str,
) -> TrustResult:
    from .crypto import decode_pubkey, decode_signature, fingerprint, verify_detached
    from .errors import OrgConfigError

    try:
        pubkey_raw = decode_pubkey(pubkey_b64)
        sig = decode_signature(signature)
    except OrgConfigError as exc:
        raise OrgConfigTrustError(str(exc)) from exc

    fp = fingerprint(pubkey_raw)
    if pinned_fingerprint is not None and fp != pinned_fingerprint:
        raise OrgConfigTrustError(
            f"public key changed (pinned {pinned_fingerprint}, got {fp}); "
            "run `aec org trust-rotate <org-id>` to acknowledge the new key"
        )
    if not verify_detached(pubkey_raw, sig, config_bytes):
        raise OrgConfigTrustError(
            "signature verification failed: config does not match its signature"
        )
    return TrustResult(trust_mode=trust_mode, acknowledged=True, pubkey_fingerprint=fp)
