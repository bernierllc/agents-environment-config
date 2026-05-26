"""Key-rotation grace / countdown / lockout state machine.

When a signed org config's public key changes, we don't silently trust the
new key, but we also don't immediately lock the user out. Instead we record
the change (``key_rotation_pending`` on the org state) and give the operator
a grace window to acknowledge it via ``aec org trust-rotate <org-id>``.

Behavior over the grace window (decision #5, user-driven rotation):

  * **clear**  — no pending rotation.
  * **warn**   — within the grace window; warn on every invocation and show a
                 day countdown.
  * **locked** — grace window elapsed; org-config operations are blocked until
                 the operator runs ``aec org trust-rotate``.

``rotation_status`` is a pure function of ``(pending, now)`` so it is trivially
testable and has no IO.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Union

ROTATION_GRACE_DAYS = 30


@dataclass(frozen=True)
class RotationStatus:
    state: str  # "clear" | "warn" | "locked"
    days_remaining: int
    message: str


def _parse(value: Union[str, datetime]) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def rotation_status(
    *,
    pending: Optional[dict],
    now: Union[str, datetime],
    org_id: Optional[str] = None,
) -> RotationStatus:
    if not pending:
        return RotationStatus(state="clear", days_remaining=ROTATION_GRACE_DAYS, message="")

    detected_at = _parse(pending["detected_at"])
    now_dt = _parse(now)

    elapsed_days = (now_dt - detected_at).days
    remaining = ROTATION_GRACE_DAYS - elapsed_days

    org_label = org_id or "<org-id>"
    detected_date = detected_at.date().isoformat()

    if remaining <= 0:
        message = (
            f"Org '{org_label}' signing key changed on {detected_date} and has been "
            f"unacknowledged for over {ROTATION_GRACE_DAYS} days; org-config operations "
            f"are LOCKED until you run `aec org trust-rotate {org_label}`."
        )
        return RotationStatus(state="locked", days_remaining=0, message=message)

    message = (
        f"Org '{org_label}' signing key changed on {detected_date}. Run "
        f"`aec org trust-rotate {org_label}` within {remaining} days or org-config "
        f"operations will be locked out."
    )
    return RotationStatus(state="warn", days_remaining=remaining, message=message)
