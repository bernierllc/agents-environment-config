import pytest

from aec.lib.org_config.errors import OrgConfigTrustError
from aec.lib.org_config.trust import (
    UnsignedConsent,
    UnsignedConsentDeclined,
    verify_trust,
)


def test_unsigned_with_consent_passes():
    result = verify_trust(
        trust_mode="unsigned",
        config_bytes=b"x",
        consent=UnsignedConsent(acknowledged=True),
    )
    assert result.acknowledged is True


def test_unsigned_without_consent_raises():
    with pytest.raises(UnsignedConsentDeclined):
        verify_trust(
            trust_mode="unsigned",
            config_bytes=b"x",
            consent=UnsignedConsent(acknowledged=False),
        )


def test_signed_modes_rejected_in_phase_1():
    with pytest.raises(OrgConfigTrustError, match="phase 2"):
        verify_trust(
            trust_mode="dns_anchor",
            config_bytes=b"x",
            consent=UnsignedConsent(acknowledged=True),
        )

    with pytest.raises(OrgConfigTrustError, match="phase 2"):
        verify_trust(
            trust_mode="pinned_key",
            config_bytes=b"x",
            consent=UnsignedConsent(acknowledged=True),
        )


def test_unknown_trust_mode_rejected():
    with pytest.raises(OrgConfigTrustError, match="unknown trust_mode"):
        verify_trust(
            trust_mode="xyzzy",
            config_bytes=b"x",
            consent=UnsignedConsent(acknowledged=True),
        )
