"""Hohmann transfer between coplanar circular orbits (two-body, impulsive)."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np

from node_api.errors import InfeasibleProblemError
from node_api.lib.solvers.lambert import keplerian_to_pv_m
from node_api.types.common import Vector3
from node_api.types.frames import Frame
from node_api.types.maneuver import BurnFrame, Maneuver, ManeuverPlan, PlanOrigin
from node_api.types.state import KeplerianElements, StateVector
from node_api.types.time import Epoch, TimeScale
from node_api.physics_runtime import ensure_physics_importable

ensure_physics_importable()
from physics.propulsion.util_dyn import mu_E as _MU_EARTH_SI  # noqa: E402


def solve_hohmann_transfer(
    initial_orbit: KeplerianElements,
    final_semi_major_axis_km: float,
    *,
    sat_id: str = "SAT",
    mu_m3_s2: float | None = None,
    departure_instant_utc: datetime | None = None,
) -> ManeuverPlan:
    """Two tangential burns: circular initial ``a`` to circular final ``a`` (same plane).

    Departure at **true anomaly 0** on the initial orbit; arrival at **true anomaly π** on
    the final circular orbit (opposite side of the departure node on the transfer ellipse).

    Raises:
        InfeasibleProblemError: If radii are invalid or transfer is non-elliptic.
    """
    mu = float(_MU_EARTH_SI if mu_m3_s2 is None else mu_m3_s2)

    r1_m = initial_orbit.semi_major_axis_km * 1000.0
    r2_m = float(final_semi_major_axis_km) * 1000.0
    if r1_m <= 0 or r2_m <= 0:
        msg = "Semi-major axes must be positive."
        raise InfeasibleProblemError(msg)
    if abs(r1_m - r2_m) < 1.0:
        msg = "Initial and final orbits are effectively identical."
        raise InfeasibleProblemError(msg)

    a_t = (r1_m + r2_m) / 2.0
    if a_t <= 0:
        raise InfeasibleProblemError("Invalid transfer semi-major axis.")

    vper = math.sqrt(mu * (2.0 / r1_m - 1.0 / a_t))
    vapo = math.sqrt(mu * (2.0 / r2_m - 1.0 / a_t))
    vcf = math.sqrt(mu / r2_m)

    dep_el = KeplerianElements(
        semi_major_axis_km=initial_orbit.semi_major_axis_km,
        eccentricity=initial_orbit.eccentricity,
        inclination_rad=initial_orbit.inclination_rad,
        raan_rad=initial_orbit.raan_rad,
        arg_perigee_rad=initial_orbit.arg_perigee_rad,
        true_anomaly_rad=0.0,
    )
    arr_el = KeplerianElements(
        semi_major_axis_km=final_semi_major_axis_km,
        eccentricity=initial_orbit.eccentricity,
        inclination_rad=initial_orbit.inclination_rad,
        raan_rad=initial_orbit.raan_rad,
        arg_perigee_rad=initial_orbit.arg_perigee_rad,
        true_anomaly_rad=math.pi,
    )

    _r1, v_circ_dep = keplerian_to_pv_m(dep_el, mu)
    _r2, v_circ_arr = keplerian_to_pv_m(arr_el, mu)

    v_hat_dep = v_circ_dep / np.linalg.norm(v_circ_dep)
    v_hat_arr = v_circ_arr / np.linalg.norm(v_circ_arr)

    v_trans_dep = vper * v_hat_dep
    v_trans_arr = vapo * v_hat_arr

    dv1_mps = v_trans_dep - v_circ_dep
    dv2_mps = v_circ_arr - v_trans_arr

    dv1 = float(np.linalg.norm(dv1_mps))
    dv2 = float(np.linalg.norm(dv2_mps))
    total = dv1 + dv2

    tof_s = math.pi * math.sqrt(a_t**3 / mu)

    t0 = departure_instant_utc or datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    if t0.tzinfo is None:
        msg = "departure_instant_utc must be timezone-aware if provided."
        raise ValueError(msg)
    dep_epoch = Epoch(instant=t0.astimezone(timezone.utc), scale=TimeScale.UTC)
    arr_epoch = Epoch(
        instant=(t0 + timedelta(seconds=tof_s)).astimezone(timezone.utc),
        scale=TimeScale.UTC,
    )

    frame = Frame.ECI_J2000
    post = StateVector(
        position_km=Vector3(data=np.asarray(_r2, dtype=np.float64) / 1000.0),
        velocity_km_s=Vector3(data=np.asarray(v_circ_arr, dtype=np.float64) / 1000.0),
        epoch=arr_epoch,
        frame=frame,
    )

    maneuvers = [
        Maneuver(epoch=dep_epoch, delta_v=Vector3(data=dv1_mps), frame=BurnFrame.ECI),
        Maneuver(epoch=arr_epoch, delta_v=Vector3(data=dv2_mps), frame=BurnFrame.ECI),
    ]

    return ManeuverPlan(
        sat_id=sat_id,
        maneuvers=maneuvers,
        total_delta_v_mps=total,
        total_fuel_kg=0.0,
        objective="hohmann_two_impulse_circular",
        predicted_post_state=post,
        generated_by=PlanOrigin.SOLVER,
        generated_at=dep_epoch,
        validation_results=[],
        time_of_flight_s=tof_s,
    )
