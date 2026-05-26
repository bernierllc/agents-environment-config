"""Date gating for time-bounded item stances (Phase 4b).

Pure helpers over ISO-8601 strings. An item with ``required_after`` only takes
effect once that instant has passed; an item with ``expires_at`` stops taking
effect at that instant. Bounds are inclusive at the lower edge and exclusive at
the upper edge: active iff ``required_after <= now < expires_at``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Union

When = Union[str, datetime]


def parse_iso(value: When) -> datetime:
    """Parse an ISO-8601 string (or pass through a datetime) to aware UTC.

    Accepts a trailing ``Z`` (Python 3.9's ``fromisoformat`` does not) and
    treats naive values as UTC so comparisons are always well-defined.
    """
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def active_at(
    now: When,
    required_after: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> bool:
    """Whether a rule is in effect at ``now`` given its optional bounds."""
    moment = parse_iso(now)
    if required_after is not None and moment < parse_iso(required_after):
        return False
    if expires_at is not None and moment >= parse_iso(expires_at):
        return False
    return True
