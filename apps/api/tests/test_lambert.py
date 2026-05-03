"""Lambert / ΔV between Keplerian orbits."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from node_api.lib.solvers.lambert import (
    _lambert_vallado,
    delta_v_between_keplerian_orbits,
    solve_lambert_problem,
)
from node_api.types.common import Vector3
from node_api.types.frames import Frame
from node_api.types.state import KeplerianElements, StateVector
from node_api.types.time import Epoch, TimeScale


def _epoch(utc: datetime) -> Epoch:
    return Epoch(instant=utc, scale=TimeScale.UTC)


def test_lambert_vallado_poliastro_example() -> None:
    """Book-style example; ~poliastro vallado reference output in km/s."""
    k = 398600.4418e9  # m^3/s^2 (mu in SI)
    r0 = np.array([5000e3, 10000e3, 2100e3], dtype=np.float64)
    r = np.array([-14600e3, 2500e3, 7000e3], dtype=np.float64)
    tof = 3600.0
    v0, v = _lambert_vallado(r0, r, tof, k, prograde=True)
    v0_km_s = v0 / 1000.0
    v_km_s = v / 1000.0
    assert np.allclose(
        v0_km_s,
        np.array([-5.99249503, 1.92536671, 3.24563805]),
        rtol=1e-5,
        atol=1e-5,
    )
    assert np.allclose(
        v_km_s,
        np.array([-3.31245851, -4.19661901, -0.38528906]),
        rtol=1e-5,
        atol=1e-5,
    )


def test_solve_lambert_problem_intercept() -> None:
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=1)
    dep = StateVector(
        position_km=Vector3(data=np.array([5000.0, 10000.0, 2100.0])),
        velocity_km_s=Vector3(data=np.array([2.0, 1.0, -0.5])),
        epoch=_epoch(t0),
        frame=Frame.ECI_J2000,
    )
    plan = solve_lambert_problem(
        dep,
        Vector3(data=np.array([-14600.0, 2500.0, 7000.0])),
        _epoch(t1),
        prograde=True,
        sat_id="TEST-1",
        mu_m3_s2=398600.4418e9,
    )
    assert plan.sat_id == "TEST-1"
    assert plan.total_delta_v_mps == pytest.approx(float(np.linalg.norm(plan.maneuvers[0].delta_v.data)))
    assert len(plan.maneuvers) == 1
    assert plan.predicted_post_state.frame == Frame.ECI_J2000


def test_equatorial_circular_7000_to_8000_km() -> None:
    """Simple smoke test: coplanar circular raise a=7000 km → a=8000 km (equatorial)."""
    from physics.propulsion import util_dyn

    mu = util_dyn.mu_E
    e_circ = 1e-8
    inc = 0.0
    t0 = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=3600)

    dep = KeplerianElements(
        semi_major_axis_km=7000.0,
        eccentricity=e_circ,
        inclination_rad=inc,
        raan_rad=0.0,
        arg_perigee_rad=0.0,
        true_anomaly_rad=0.0,
    )
    # Different phase so initial/final radii are not collinear (Lambert needs a plane).
    arr = KeplerianElements(
        semi_major_axis_km=8000.0,
        eccentricity=e_circ,
        inclination_rad=inc,
        raan_rad=0.0,
        arg_perigee_rad=0.0,
        true_anomaly_rad=float(np.pi / 2),
    )

    plan = delta_v_between_keplerian_orbits(
        dep,
        arr,
        _epoch(t0),
        _epoch(t1),
        "EQ-RAISE",
        mu_m3_s2=mu,
        prograde=True,
    )

    assert len(plan.maneuvers) == 2
    assert plan.total_delta_v_mps > 0.0
    assert plan.total_delta_v_mps < 15_000.0  # sanity (LEO-scale transfer, not escape)


def test_delta_v_same_orbit_consistent_phasing_small_dv() -> None:
    """Two-body coast along one ellipse: propagated mean anomaly gives arrival state; Δv ≈ 0."""
    from physics.propulsion import util_dyn

    a_m = 7000e3
    e = 0.001
    inc = np.radians(60.0)
    mu = util_dyn.mu_E
    oe0 = np.array([a_m, e, inc, 0.0, 0.0, 0.0], dtype=np.float64)
    oe1 = util_dyn.propagate_oe(oe0, 3600.0, mu=mu, J2=0.0)
    nu0 = util_dyn.mean_to_true_anomaly(float(oe0[5]), e)
    nu1 = util_dyn.mean_to_true_anomaly(float(oe1[5]), e)
    t0 = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=1)
    dep = KeplerianElements(
        semi_major_axis_km=a_m / 1000.0,
        eccentricity=e,
        inclination_rad=inc,
        raan_rad=0.0,
        arg_perigee_rad=0.0,
        true_anomaly_rad=float(nu0),
    )
    arr = KeplerianElements(
        semi_major_axis_km=a_m / 1000.0,
        eccentricity=e,
        inclination_rad=inc,
        raan_rad=float(np.mod(oe1[3], 2 * np.pi)),
        arg_perigee_rad=float(np.mod(oe1[4], 2 * np.pi)),
        true_anomaly_rad=float(nu1),
    )
    plan = delta_v_between_keplerian_orbits(
        dep,
        arr,
        _epoch(t0),
        _epoch(t1),
        "PHASE",
        mu_m3_s2=mu,
    )
    assert len(plan.maneuvers) == 2
    assert plan.total_delta_v_mps == pytest.approx(0.0, abs=1e-3)
    assert plan.objective == "lambert_two_impulse_keplerian"
