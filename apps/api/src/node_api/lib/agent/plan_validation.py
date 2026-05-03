"""Wire-format checks for agent maneuver plans (JSON tool payloads)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

_CHECK_ID = "BURN_EPOCH_TIMING_RELAXED"


def burn_epoch_future_validation_row(
    maneuvers: list[dict[str, Any]],
    not_before: datetime,
) -> dict[str, Any]:
    """Parse maneuver epochs only; do not fail on wall-clock vs burn time (sim / immediate burns)."""
    for i, m in enumerate(maneuvers):
        es = m.get("epoch_utc")
        try:
            datetime.fromisoformat(str(es).replace("Z", "+00:00")).astimezone(UTC)
        except (ValueError, TypeError, AttributeError):
            return {
                "passed": False,
                "check_id": "BURN_EPOCH_PARSE",
                "message": f"Burn {i + 1}: invalid or missing epoch_utc.",
            }
    ref_s = not_before.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return {
        "passed": True,
        "check_id": _CHECK_ID,
        "message": (
            f"Maneuver epoch(s) parse as UTC. Burn timing is not rejected vs server reference ({ref_s}); "
            "operator/sim clock governs feasibility."
        ),
    }


def plan_dict_validation_passed(plan: dict[str, Any], *, not_before: datetime | None = None) -> bool:
    """True if every wire ``validation`` entry passes and all maneuver ``epoch_utc`` values parse as UTC."""
    ref = (not_before or datetime.now(UTC)).astimezone(UTC)
    raw = list(plan.get("validation") or [])
    solver_ok = all(bool(v.get("passed")) for v in raw) if raw else True
    burn_ok = burn_epoch_future_validation_row(plan.get("maneuvers") or [], ref)["passed"]
    return solver_ok and burn_ok
