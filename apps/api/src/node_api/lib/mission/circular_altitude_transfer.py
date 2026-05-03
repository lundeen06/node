"""Coplanar circular altitude change: Lambert transfer arc + circularization (two ECI impulsive burns)."""

from __future__ import annotations

import math
from datetime import timedelta, timezone

import numpy as np
from numpy.typing import NDArray

from node_api.errors import InfeasibleProblemError
from node_api.lib.solvers.lambert import _lambert_vallado
from node_api.physics_runtime import ensure_physics_importable
from node_api.types.common import Vector3
from node_api.types.frames import Frame
from node_api.types.maneuver import BurnFrame, Maneuver, ManeuverPlan, PlanOrigin, ValidationOutcome
from node_api.types.state import StateVector
from node_api.types.time import Epoch, TimeScale

ensure_physics_importable()
from physics.propulsion.util_dyn import R_E as _R_E_M, mu_E as _MU_E  # noqa: E402


def plan_lambert_two_burn_circular_altitude_change(
    r1_m: NDArray[np.float64],
    v1_mps: NDArray[np.float64],
    target_circular_altitude_km: float,
    departure_epoch: Epoch,
    sat_id: str,
    *,
    earth_radius_m: float | None = None,
) -> ManeuverPlan:
    """Two-body, coplanar: SGP4 state at departure, target circular orbit at ``altitude + R_E``.

    Uses a **Lambert** arc from current position to the point on the target circle **180° away**
    (Hohmann-like geometry), then a second impulsive burn to match circular speed and direction.

    Position/velocity are ECI-like (same frame as SGP4 TEME used elsewhere in this API).
    """
    mu = float(_MU_E)
    r_e = float(_R_E_M if earth_radius_m is None else earth_radius_m)

    r1 = np.asarray(r1_m, dtype=np.float64).reshape(3)
    v1 = np.asarray(v1_mps, dtype=np.float64).reshape(3)
    r1_mag = float(np.linalg.norm(r1))
    if r1_mag < 1e4:
        msg = "Departure radius is unrealistically small."
        raise InfeasibleProblemError(msg)

    r2_mag = r_e + float(target_circular_altitude_km) * 1000.0
    if r2_mag <= r_e + 80_000.0:
        msg = "Target altitude must leave the satellite well above sensible atmosphere (> ~80 km)."
        raise InfeasibleProblemError(msg)

    if abs(r2_mag - r1_mag) < 500.0:
        msg = "Initial radius and target circular radius are too close for a meaningful transfer."
        raise InfeasibleProblemError(msg)

    r2 = -(r2_mag / r1_mag) * r1

    a_t = (r1_mag + r2_mag) / 2.0
    if a_t <= 0:
        raise InfeasibleProblemError("Invalid transfer semi-major axis.")
    tof_s = math.pi * math.sqrt(a_t**3 / mu)
    if tof_s <= 0 or not math.isfinite(tof_s):
        raise InfeasibleProblemError("Invalid time of flight for transfer.")

    h = np.cross(r1, v1)
    norm_h = float(np.linalg.norm(h))
    if norm_h < 1e-3:
        msg = "Degenerate orbit (position and velocity nearly collinear)."
        raise InfeasibleProblemError(msg)
    h_dir = h / norm_h

    def circular_velocity_at_r2(v_transfer_arrival: NDArray[np.float64]) -> NDArray[np.float64]:
        along = np.cross(h_dir, r2)
        la = float(np.linalg.norm(along))
        if la < 1e-20:
            msg = "Cannot resolve circular velocity direction at arrival."
            raise InfeasibleProblemError(msg)
        u = along / la
        if float(np.dot(u, v_transfer_arrival)) < 0.0:
            u = -u
        vc_mag = math.sqrt(mu / r2_mag)
        return u * vc_mag

    best: tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]] | None = None
    best_cost = float("inf")
    for prograde in (True, False):
        try:
            v1p, v2m = _lambert_vallado(r1, r2, tof_s, mu, prograde=prograde)
        except InfeasibleProblemError:
            continue
        v_circ = circular_velocity_at_r2(v2m)
        dv1 = v1p - v1
        dv2 = v_circ - v2m
        cost = float(np.linalg.norm(dv1) + np.linalg.norm(dv2))
        if cost < best_cost:
            best_cost = cost
            best = (dv1, dv2, v_circ)

    if best is None:
        msg = "Lambert transfer leg is infeasible for this geometry and time of flight."
        raise InfeasibleProblemError(msg)

    dv1_mps, dv2_mps, v_circ = best

    t0 = departure_epoch.as_utc_datetime()
    arr_instant = (t0 + timedelta(seconds=tof_s)).astimezone(timezone.utc)
    arr_epoch = Epoch(instant=arr_instant, scale=TimeScale.UTC)

    maneuvers = [
        Maneuver(epoch=departure_epoch, delta_v=Vector3(data=dv1_mps), frame=BurnFrame.ECI),
        Maneuver(epoch=arr_epoch, delta_v=Vector3(data=dv2_mps), frame=BurnFrame.ECI),
    ]

    post = StateVector(
        position_km=Vector3(data=r2 / 1000.0),
        velocity_km_s=Vector3(data=v_circ / 1000.0),
        epoch=arr_epoch,
        frame=Frame.ECI_J2000,
    )

    total = float(np.linalg.norm(dv1_mps) + np.linalg.norm(dv2_mps))
    val = ValidationOutcome(
        check_id="lambert_two_burn_altitude",
        passed=True,
        message=(
            f"Coplanar Lambert leg ({tof_s / 60:.1f} min) then circularization at "
            f"alt ≈ {target_circular_altitude_km:.1f} km (spherical R_E)."
        ),
    )

    return ManeuverPlan(
        sat_id=sat_id,
        maneuvers=maneuvers,
        total_delta_v_mps=total,
        total_fuel_kg=0.0,
        objective="lambert_two_burn_circular_altitude_change",
        predicted_post_state=post,
        generated_by=PlanOrigin.SOLVER,
        generated_at=Epoch(
            instant=departure_epoch.instant.astimezone(timezone.utc),
            scale=departure_epoch.scale,
        ),
        validation_results=[val],
        time_of_flight_s=tof_s,
    )
