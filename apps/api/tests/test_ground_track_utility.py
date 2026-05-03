"""Ground-track RMSE vs nominal TLE and mission loss / utility."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from node_api.lib.geodesy import great_circle_distance_km
from node_api.lib.mission.ground_track_utility import (
    combined_mission_loss,
    ground_track_deviation_report,
    orbit_dual_deviation_report,
    orbit_utility_breakdown,
    utility_exponential_rmse,
)
from node_api.physics_runtime import ensure_physics_importable

ensure_physics_importable()

_ISS_LINE1 = "1 25544U 98067A   24180.25000000  .00016717  00000+0  10270-3 0  9990"
_ISS_LINE2 = "2 25544  51.6416 355.6478 0007418  43.0265 317.0558 15.49408543 45756"


def test_great_circle_equator_one_degree() -> None:
    d = great_circle_distance_km(0.0, 0.0, 1.0, 0.0)
    assert 110.0 < d < 112.0


def test_identical_tles_near_zero_parallel_loss() -> None:
    t0 = datetime(2024, 6, 28, 6, 0, 0, tzinfo=UTC)
    t1 = datetime(2024, 6, 28, 12, 0, 0, tzinfo=UTC)
    rep = ground_track_deviation_report(
        _ISS_LINE1,
        _ISS_LINE2,
        _ISS_LINE1,
        _ISS_LINE2,
        t0,
        t1,
        n_samples=24,
    )
    assert rep.rmse_km < 1e-6
    assert rep.mse_km2 < 1e-12
    dual = orbit_dual_deviation_report(
        _ISS_LINE1,
        _ISS_LINE2,
        _ISS_LINE1,
        _ISS_LINE2,
        t0,
        t1,
        n_samples=24,
    )
    assert dual.eci_position.rmse_km < 1e-6
    assert dual.ground_track.rmse_km == pytest.approx(rep.rmse_km)


def test_utility_and_combined_loss_monotone() -> None:
    assert utility_exponential_rmse(0.0, 25.0) == 1.0
    u_small = utility_exponential_rmse(5.0, 25.0)
    u_large = utility_exponential_rmse(50.0, 25.0)
    assert u_small > u_large

    l0 = combined_mission_loss(10.0, 50.0, 100.0, length_scale_km=25.0)
    l_over = combined_mission_loss(10.0, 150.0, 100.0, length_scale_km=25.0)
    assert l_over > l0

    l_eci_only = combined_mission_loss(
        0.0,
        50.0,
        100.0,
        length_scale_km=25.0,
        rmse_eci_km=10.0,
        length_scale_eci_km=5.0,
        w_eci=1.0,
    )
    assert l_eci_only == pytest.approx(2.0)


def test_orbit_utility_breakdown_shape() -> None:
    t0 = datetime(2024, 6, 28, 6, 0, 0, tzinfo=UTC)
    t1 = datetime(2024, 6, 28, 8, 0, 0, tzinfo=UTC)
    b = orbit_utility_breakdown(
        _ISS_LINE1,
        _ISS_LINE2,
        _ISS_LINE1,
        _ISS_LINE2,
        t0,
        t1,
        delta_v_used_mps=20.0,
        delta_v_budget_mps=100.0,
        n_samples=12,
        length_scale_track_km=25.0,
        length_scale_eci_km=5.0,
    )
    assert b.utility_unitless == 1.0
    assert b.utility_ground_track_unitless == 1.0
    assert b.utility_eci_position_unitless == 1.0
    assert b.eci_position_rmse_km < 1e-6
    assert b.fuel_overrun_mps == 0.0
    assert b.track_opportunity_cost == 0.0
    assert b.eci_opportunity_cost == 0.0
