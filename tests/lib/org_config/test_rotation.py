"""Tests for the key-rotation grace/countdown/lockout state machine."""

import pytest

from aec.lib.org_config.rotation import (
    ROTATION_GRACE_DAYS,
    rotation_status,
)


def _pending(detected_at):
    return {
        "detected_at": detected_at,
        "new_fingerprint": "SHA256:new",
        "old_fingerprint": "SHA256:old",
    }


def test_no_pending_returns_clear():
    status = rotation_status(pending=None, now="2026-05-24T00:00:00Z")
    assert status.state == "clear"
    assert status.days_remaining == ROTATION_GRACE_DAYS


def test_pending_within_grace_warns_with_countdown():
    status = rotation_status(
        pending=_pending("2026-05-01T00:00:00Z"),
        now="2026-05-24T00:00:00Z",
    )
    assert status.state == "warn"
    assert status.days_remaining == 7  # 30 - 23
    assert "trust-rotate" in status.message
    assert "7" in status.message


def test_just_detected_has_full_grace():
    status = rotation_status(
        pending=_pending("2026-05-24T00:00:00Z"),
        now="2026-05-24T00:00:00Z",
    )
    assert status.state == "warn"
    assert status.days_remaining == ROTATION_GRACE_DAYS


def test_pending_at_grace_boundary_locks_out():
    status = rotation_status(
        pending=_pending("2026-04-24T00:00:00Z"),
        now="2026-05-24T00:00:00Z",
    )
    assert status.state == "locked"
    assert status.days_remaining == 0


def test_pending_past_grace_locks_out():
    status = rotation_status(
        pending=_pending("2026-04-01T00:00:00Z"),
        now="2026-05-24T00:00:00Z",
    )
    assert status.state == "locked"
    assert status.days_remaining == 0
    assert "locked" in status.message.lower()


def test_accepts_datetime_for_now():
    from datetime import datetime, timezone

    status = rotation_status(
        pending=_pending("2026-05-20T00:00:00Z"),
        now=datetime(2026, 5, 24, tzinfo=timezone.utc),
    )
    assert status.state == "warn"
    assert status.days_remaining == 26


def test_org_id_appears_in_message_when_given():
    status = rotation_status(
        pending=_pending("2026-05-24T00:00:00Z"),
        now="2026-05-24T00:00:00Z",
        org_id="acme",
    )
    assert "acme" in status.message
