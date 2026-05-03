"""Agent plan wire validation (burn epoch parsing; solver validation rows)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from node_api.lib.agent.plan_validation import (
    burn_epoch_future_validation_row,
    plan_dict_validation_passed,
)


def test_burn_epoch_future_passes_when_burns_after_reference() -> None:
    ref = datetime(2030, 1, 1, 12, 0, 0, tzinfo=UTC)
    row = burn_epoch_future_validation_row(
        [{"epoch_utc": "2030-01-01T13:00:00Z"}],
        ref,
    )
    assert row["passed"] is True


def test_burn_epoch_before_reference_still_passes_relaxed_timing() -> None:
    ref = datetime(2030, 1, 1, 12, 0, 0, tzinfo=UTC)
    row = burn_epoch_future_validation_row(
        [{"epoch_utc": "2030-01-01T11:00:00Z"}],
        ref,
    )
    assert row["passed"] is True
    assert row["check_id"] == "BURN_EPOCH_TIMING_RELAXED"


def test_plan_dict_validation_passed_true_when_burn_before_reference_and_validation_empty() -> None:
    ref = datetime(2030, 6, 1, 0, 0, 0, tzinfo=UTC)
    plan = {
        "maneuvers": [{"epoch_utc": "2030-05-01T00:00:00Z"}],
        "validation": [],
    }
    assert plan_dict_validation_passed(plan, not_before=ref) is True


def test_plan_dict_validation_passed_true_when_solver_and_burns_ok() -> None:
    ref = datetime(2030, 1, 1, 12, 0, 0, tzinfo=UTC)
    plan = {
        "maneuvers": [{"epoch_utc": "2030-01-01T13:00:00Z"}],
        "validation": [{"passed": True, "check_id": "x", "message": "ok"}],
    }
    assert plan_dict_validation_passed(plan, not_before=ref) is True


def test_burn_epoch_parses_when_slightly_before_reference() -> None:
    ref = datetime(2030, 1, 1, 12, 0, 0, tzinfo=UTC)
    almost = ref - timedelta(milliseconds=500)
    row = burn_epoch_future_validation_row(
        [{"epoch_utc": almost.isoformat().replace("+00:00", "Z")}],
        ref,
    )
    assert row["passed"] is True
