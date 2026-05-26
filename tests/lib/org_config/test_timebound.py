"""Tests for time-bounded rule date gating (Phase 4b)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from aec.lib.org_config.timebound import active_at, parse_iso


def _utc(y, m, d, hh=0, mm=0, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc)


class TestParseIso:
    def test_full_datetime_with_offset(self):
        assert parse_iso("2026-06-01T12:00:00+00:00") == _utc(2026, 6, 1, 12)

    def test_z_suffix_is_treated_as_utc(self):
        assert parse_iso("2026-06-01T12:00:00Z") == _utc(2026, 6, 1, 12)

    def test_date_only_is_midnight_utc(self):
        assert parse_iso("2026-06-01") == _utc(2026, 6, 1)

    def test_naive_datetime_assumed_utc(self):
        assert parse_iso("2026-06-01T08:30:00") == _utc(2026, 6, 1, 8, 30)

    def test_invalid_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_iso("not-a-date")


class TestActiveAt:
    def test_no_bounds_is_always_active(self):
        assert active_at(_utc(2026, 1, 1)) is True

    def test_before_required_after_is_inactive(self):
        assert active_at(_utc(2026, 5, 1), required_after="2026-06-01") is False

    def test_at_required_after_is_active_inclusive(self):
        assert active_at(_utc(2026, 6, 1), required_after="2026-06-01") is True

    def test_after_required_after_is_active(self):
        assert active_at(_utc(2026, 7, 1), required_after="2026-06-01") is True

    def test_before_expiry_is_active(self):
        assert active_at(_utc(2026, 5, 1), expires_at="2026-06-01") is True

    def test_at_expiry_is_inactive_exclusive(self):
        assert active_at(_utc(2026, 6, 1), expires_at="2026-06-01") is False

    def test_after_expiry_is_inactive(self):
        assert active_at(_utc(2026, 7, 1), expires_at="2026-06-01") is False

    def test_inside_window_is_active(self):
        assert (
            active_at(
                _utc(2026, 6, 15),
                required_after="2026-06-01",
                expires_at="2026-07-01",
            )
            is True
        )

    def test_z_suffixed_bounds(self):
        assert (
            active_at(
                _utc(2026, 6, 15, 12),
                required_after="2026-06-01T00:00:00Z",
                expires_at="2026-07-01T00:00:00Z",
            )
            is True
        )

    def test_now_accepts_iso_string(self):
        assert active_at("2026-06-15", required_after="2026-06-01") is True

    def test_naive_now_treated_as_utc(self):
        assert active_at(datetime(2026, 6, 15), required_after="2026-06-01") is True
