"""Hybrid burn utility preview (SGP4 nominal vs two-body after ECI impulses)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

from node_api.lib.mission.burn_utility_preview import preview_plan_utility_vs_catalog_tle
from node_api.physics_runtime import ensure_physics_importable
from node_api.types.common import Vector3
from node_api.types.maneuver import BurnFrame, Maneuver
from node_api.types.time import Epoch, TimeScale

ensure_physics_importable()

_ISS_LINE1 = "1 25544U 98067A   24180.25000000  .00016717  00000+0  10270-3 0  9990"
_ISS_LINE2 = "2 25544  51.6416 355.6478 0007418  43.0265 317.0558 15.49408543 45756"


def test_preview_returns_parallel_metrics_and_utility() -> None:
    t_burn = datetime(2024, 6, 28, 12, 0, 0, tzinfo=UTC)
    m = Maneuver(
        epoch=Epoch(instant=t_burn, scale=TimeScale.UTC),
        delta_v=Vector3(data=np.array([2.0, 0.0, 0.0], dtype=np.float64)),
        frame=BurnFrame.ECI,
    )
    out = preview_plan_utility_vs_catalog_tle(
        _ISS_LINE1,
        _ISS_LINE2,
        [m],
        t0_utc=t_burn,
        t1_utc=t_burn + timedelta(hours=6),
        n_samples=16,
        delta_v_budget_mps=100.0,
        delta_v_used_mps=2.0,
    )
    assert "error" not in out
    assert out["parallel_deviation"]["ground_track"]["rmse_km"] >= 0.0
    assert out["parallel_deviation"]["eci_position"]["rmse_km"] >= 0.0
    assert "calibration" in out and "integrated_loss" in out
    u = out["utility_and_loss"]["utility_unitless"]
    assert 0.0 < u <= 1.0


def test_preview_rejects_non_eci_frame() -> None:
    t_burn = datetime(2024, 6, 28, 12, 0, 0, tzinfo=UTC)
    m = Maneuver(
        epoch=Epoch(instant=t_burn, scale=TimeScale.UTC),
        delta_v=Vector3(data=np.array([1.0, 0.0, 0.0], dtype=np.float64)),
        frame=BurnFrame.RIC,
    )
    out = preview_plan_utility_vs_catalog_tle(
        _ISS_LINE1,
        _ISS_LINE2,
        [m],
        t0_utc=t_burn,
        t1_utc=t_burn + timedelta(hours=1),
        n_samples=4,
        delta_v_budget_mps=50.0,
    )
    assert out.get("error")
