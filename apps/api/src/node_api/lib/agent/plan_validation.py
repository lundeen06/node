"""Wire-format checks for agent maneuver plans (JSON tool payloads)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

_BURN_MARGIN = timedelta(seconds=1.0)
_CHECK_ID = "BURN_EPOCH_NOT_IN_PAST"


def burn_epoch_future_validation_row(
    maneuvers: list[dict[str, Any]],
    not_before: datetime,
) -> dict[str, Any]:
    """Return one validation dict: passed iff every maneuver epoch parses and is >= ``not_before`` (minus margin)."""
    threshold = not_before.astimezone(UTC) - _BURN_MARGIN
    for i, m in enumerate(maneuvers):
        es = m.get("epoch_utc")
        try:
            ep = datetime.fromisoformat(str(es).replace("Z", "+00:00")).astimezone(UTC)
        except (ValueError, TypeError, AttributeError):
            return {
                "passed": False,
                "check_id": "BURN_EPOCH_PARSE",
                "message": f"Burn {i + 1}: invalid or missing epoch_utc.",
            }
        if ep < threshold:
            ref_s = not_before.astimezone(UTC).isoformat().replace("+00:00", "Z")
            return {
                "passed": False,
                "check_id": _CHECK_ID,
                "message": (
                    f"Burn {i + 1} at {es!r} is before the planning reference UTC ({ref_s}); "
                    "maneuvers must not be in the past."
                ),
            }
    ref_s = not_before.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return {
        "passed": True,
        "check_id": _CHECK_ID,
        "message": (
            f"All maneuver epochs are at or after the planning reference ({ref_s}, 1 s tolerance)."
        ),
    }


def plan_dict_validation_passed(plan: dict[str, Any], *, not_before: datetime | None = None) -> bool:
    """True only if every wire ``validation`` entry passes and all burns are not before ``not_before``."""
    ref = (not_before or datetime.now(UTC)).astimezone(UTC)
    raw = list(plan.get("validation") or [])
    solver_ok = all(bool(v.get("passed")) for v in raw) if raw else True
    burn_ok = burn_epoch_future_validation_row(plan.get("maneuvers") or [], ref)["passed"]
    return solver_ok and burn_ok
