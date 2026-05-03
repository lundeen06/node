"""Lambert two-point boundary value solver (two-body, zero-revolution)."""

from __future__ import annotations

import math
from datetime import timezone

import numpy as np
from numpy.typing import NDArray

from node_api.errors import InfeasibleProblemError
from node_api.physics_runtime import ensure_physics_importable
from node_api.types.common import Vector3
from node_api.types.frames import Frame
from node_api.types.maneuver import BurnFrame, Maneuver, ManeuverPlan, PlanOrigin
from node_api.types.state import KeplerianElements, StateVector
from node_api.types.time import Epoch

ensure_physics_importable()
from physics.propulsion.util_dyn import mu_E as _MU_EARTH_SI  # noqa: E402
from physics.propulsion.util_dyn import oe_to_pv as _oe_to_pv  # noqa: E402


def _stumpff_c2(psi: float) -> float:
    """Second Stumpff function c_2(psi) (Vallado / Battin)."""
    eps = 1.0
    if psi > eps:
        return (1.0 - math.cos(math.sqrt(psi))) / psi
    if psi < -eps:
        return (math.cosh(math.sqrt(-psi)) - 1.0) / (-psi)
    return 0.5


def _stumpff_c3(psi: float) -> float:
    """Third Stumpff function c_3(psi)."""
    eps = 1.0
    if psi > eps:
        sq = math.sqrt(psi)
        return (sq - math.sin(sq)) / (psi * sq)
    if psi < -eps:
        sn = math.sqrt(-psi)
        return (math.sinh(sn) - sn) / ((-psi) * sn)
    return 1.0 / 6.0


def _lambert_vallado(
    r0_m: NDArray[np.float64],
    r_m: NDArray[np.float64],
    tof_s: float,
    mu_m3_s2: float,
    *,
    prograde: bool,
    numiter: int = 60,
    rtol: float = 1e-8,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Solve Lambert's problem (Vallado universal variable + bisection on psi).

    Positions in meters, ``mu`` in m³/s², TOF in seconds; returns velocities in m/s.
    """
    if tof_s <= 0:
        msg = "Time of flight must be positive."
        raise InfeasibleProblemError(msg)
    if mu_m3_s2 <= 0:
        msg = "Gravitational parameter must be positive."
        raise InfeasibleProblemError(msg)

    r0 = np.asarray(r0_m, dtype=np.float64).reshape(3)
    r = np.asarray(r_m, dtype=np.float64).reshape(3)

    norm_r0 = float(np.linalg.norm(r0))
    norm_r = float(np.linalg.norm(r))
    cross_r = np.cross(r0, r)
    cross_norm = float(np.linalg.norm(cross_r))
    colin_thresh = 1e-6 * norm_r0 * norm_r
    if cross_norm < colin_thresh:
        # True 180° in-plane transfers are singular; nudge arrival by ~10 m perpendicular
        # to ``r0`` so the universal-variable formulation remains well-posed.
        aux = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        orth = np.cross(r0, aux)
        onorm = float(np.linalg.norm(orth))
        if onorm < 1e-12 * max(norm_r0, 1.0):
            orth = np.cross(r0, np.array([0.0, 1.0, 0.0], dtype=np.float64))
            onorm = float(np.linalg.norm(orth))
        if onorm < 1e-30:
            msg = "Lambert problem is undefined for collinear position vectors."
            raise InfeasibleProblemError(msg)
        orth = orth / onorm
        bump_m = max(10.0, colin_thresh / max(norm_r, 1.0) * 1e3)
        r = r + orth * bump_m

    t_m = 1.0 if prograde else -1.0

    norm_r = float(np.linalg.norm(r))
    norm_r0_times_norm_r = norm_r0 * norm_r
    norm_r0_plus_norm_r = norm_r0 + norm_r

    cos_dnu = float(np.dot(r0, r) / norm_r0_times_norm_r)
    cos_dnu = float(np.clip(cos_dnu, -1.0, 1.0))

    a_lane = t_m * math.sqrt(norm_r * norm_r0 * (1.0 + cos_dnu))
    if abs(a_lane) < 1e-12:
        msg = "Cannot compute Lambert arc (transfer angle ≈ 180°)."
        raise InfeasibleProblemError(msg)

    psi = 0.0
    psi_low = -4.0 * math.pi**2
    psi_up = 4.0 * math.pi**2

    y = 0.0
    count = 0
    while count < numiter:
        c2 = _stumpff_c2(psi)
        c3 = _stumpff_c3(psi)
        sqrt_c2 = math.sqrt(c2)
        y = norm_r0_plus_norm_r + a_lane * (psi * c3 - 1.0) / sqrt_c2

        if a_lane > 0.0:
            while y < 0.0:
                psi_low = psi
                psi = 0.8 * (1.0 / c3) * (1.0 - norm_r0_times_norm_r * sqrt_c2 / a_lane)
                c2 = _stumpff_c2(psi)
                c3 = _stumpff_c3(psi)
                sqrt_c2 = math.sqrt(c2)
                y = norm_r0_plus_norm_r + a_lane * (psi * c3 - 1.0) / sqrt_c2

        xi = math.sqrt(y / c2)
        tof_new = (xi**3 * c3 + a_lane * math.sqrt(y)) / math.sqrt(mu_m3_s2)

        if abs((tof_new - tof_s) / tof_s) < rtol:
            break

        count += 1
        if tof_new <= tof_s:
            psi_low = psi
        else:
            psi_up = psi
        psi = (psi_up + psi_low) / 2.0
    else:
        msg = "Lambert solver did not converge for the given geometry and time of flight."
        raise InfeasibleProblemError(msg)

    f = 1.0 - y / norm_r0
    g = a_lane * math.sqrt(y / mu_m3_s2)
    gdot = 1.0 - y / norm_r

    v0 = (r - f * r0) / g
    v = (gdot * r - r0) / g
    return np.asarray(v0, dtype=np.float64), np.asarray(v, dtype=np.float64)


def _nu_to_mean_anomaly(nu: float, ecc: float) -> float:
    """Eccentric elliptic: ν → M."""
    e = ecc
    tan_half_nu = math.tan(nu / 2.0)
    e_anom = 2.0 * math.atan(math.sqrt((1.0 - e) / (1.0 + e)) * tan_half_nu)
    return e_anom - e * math.sin(e_anom)


def _keplerian_to_oe_vector_m(elements: KeplerianElements) -> NDArray[np.float64]:
    """Classical elements as ``[a, e, i, Ω, ω, M]`` with ``a`` in meters (``oe_to_pv`` convention)."""
    a_m = elements.semi_major_axis_km * 1000.0
    e = elements.eccentricity
    inc = elements.inclination_rad
    raan = elements.raan_rad
    argp = elements.arg_perigee_rad
    if elements.true_anomaly_rad is not None:
        mean_anomaly_rad = _nu_to_mean_anomaly(elements.true_anomaly_rad, e)
    else:
        mean_anomaly_rad = float(elements.mean_anomaly_rad)
    return np.array([a_m, e, inc, raan, argp, mean_anomaly_rad], dtype=np.float64)


def keplerian_to_pv_m(elements: KeplerianElements, mu_m3_s2: float | None = None) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Convert Keplerian elements to Cartesian position (m) and velocity (m/s)."""
    mu = float(_MU_EARTH_SI if mu_m3_s2 is None else mu_m3_s2)
    oe = _keplerian_to_oe_vector_m(elements)
    pv = np.asarray(_oe_to_pv(oe, mu), dtype=np.float64).reshape(6)
    return pv[0:3], pv[3:6]


def delta_v_between_keplerian_orbits(
    departure_elements: KeplerianElements,
    arrival_elements: KeplerianElements,
    departure_epoch: Epoch,
    arrival_epoch: Epoch,
    sat_id: str,
    *,
    mu_m3_s2: float | None = None,
    prograde: bool = True,
) -> ManeuverPlan:
    """Two-body Lambert transfer between osculating Keplerian orbits at two epochs.

    Interprets ``departure_elements`` at ``departure_epoch`` and ``arrival_elements`` at
    ``arrival_epoch`` as instantaneous osculating states, converts each to Cartesian
    position, solves Lambert between those positions for the time-of-flight, and returns
    impulsive Δv at departure and at arrival to enter and exit the transfer conic.

    Returns:
        ``ManeuverPlan`` with two ECI Δv vectors (m/s), ``predicted_post_state`` on the
        target orbit at ``arrival_epoch``, and ``time_of_flight_s`` set to the solved arc
        duration ``arrival_epoch - departure_epoch``.
    """
    mu = float(_MU_EARTH_SI if mu_m3_s2 is None else mu_m3_s2)

    t0 = departure_epoch.as_utc_datetime()
    t1 = arrival_epoch.as_utc_datetime()
    tof_s = (t1 - t0).total_seconds()
    if tof_s <= 0:
        msg = "Arrival epoch must be after departure epoch."
        raise InfeasibleProblemError(msg)

    r1_m, v1_mps = keplerian_to_pv_m(departure_elements, mu)
    r2_m, v2_mps = keplerian_to_pv_m(arrival_elements, mu)

    # Vallado short-way Lambert admits two ``prograde`` directions; total Δv can
    # differ wildly (e.g. coast phasing vs the opposite branch). Take the cheaper.
    candidates: list[tuple[float, NDArray[np.float64], NDArray[np.float64]]] = []
    for pr in (prograde, not prograde):
        try:
            v1t, v2t = _lambert_vallado(r1_m, r2_m, tof_s, mu, prograde=pr)
        except InfeasibleProblemError:
            continue
        dv1 = float(np.linalg.norm(v1t - v1_mps))
        dv2 = float(np.linalg.norm(v2_mps - v2t))
        candidates.append((dv1 + dv2, v1t, v2t))
    if not candidates:
        msg = "Lambert has no feasible branch for this chord and time of flight."
        raise InfeasibleProblemError(msg)
    candidates.sort(key=lambda c: c[0])
    _best_dv, v1t_mps, v2t_mps = candidates[0]

    dv1_mps = v1t_mps - v1_mps
    dv2_mps = v2_mps - v2t_mps
    dv1_norm = float(np.linalg.norm(dv1_mps))
    dv2_norm = float(np.linalg.norm(dv2_mps))
    total_dv_mps = dv1_norm + dv2_norm

    frame = Frame.ECI_J2000
    dep_state = StateVector(
        position_km=Vector3(data=r1_m / 1000.0),
        velocity_km_s=Vector3(data=v1_mps / 1000.0),
        epoch=departure_epoch,
        frame=frame,
    )
    post_state = StateVector(
        position_km=Vector3(data=r2_m / 1000.0),
        velocity_km_s=Vector3(data=v2_mps / 1000.0),
        epoch=arrival_epoch,
        frame=frame,
    )

    maneuvers = [
        Maneuver(
            epoch=departure_epoch,
            delta_v=Vector3(data=dv1_mps),
            frame=BurnFrame.ECI,
            duration_s=0.0,
        ),
        Maneuver(
            epoch=arrival_epoch,
            delta_v=Vector3(data=dv2_mps),
            frame=BurnFrame.ECI,
            duration_s=0.0,
        ),
    ]

    return ManeuverPlan(
        sat_id=sat_id,
        maneuvers=maneuvers,
        total_delta_v_mps=total_dv_mps,
        total_fuel_kg=0.0,
        objective="lambert_two_impulse_keplerian",
        predicted_post_state=post_state,
        generated_by=PlanOrigin.SOLVER,
        generated_at=Epoch(instant=departure_epoch.instant.astimezone(timezone.utc), scale=departure_epoch.scale),
        validation_results=[],
        time_of_flight_s=tof_s,
    )


def solve_lambert_problem(
    departure: StateVector,
    arrival_position_km: Vector3,
    arrival_epoch: Epoch,
    prograde: bool,
    *,
    sat_id: str = "SAT",
    mu_m3_s2: float | None = None,
) -> ManeuverPlan:
    """Solve a two-body Lambert arc between a departure state and a terminal position/time.

    Computes the impulsive maneuver at departure to inject onto the transfer conic that
    reaches ``arrival_position_km`` at ``arrival_epoch``. The predicted post-state is the
    arrival position with velocity on the **transfer** orbit (coast after the single
    maneuver). For matching a **target** osculating orbit at arrival, use
    :func:`delta_v_between_keplerian_orbits`.

    The returned plan has ``time_of_flight_s`` set to
    ``arrival_epoch - departure.epoch`` in seconds.
    """
    mu = float(_MU_EARTH_SI if mu_m3_s2 is None else mu_m3_s2)

    tof_s = (arrival_epoch.as_utc_datetime() - departure.epoch.as_utc_datetime()).total_seconds()
    if tof_s <= 0:
        msg = "Arrival epoch must be after departure epoch."
        raise InfeasibleProblemError(msg)

    r0_m = np.asarray(departure.position_km.data, dtype=np.float64).reshape(3) * 1000.0
    r_m = np.asarray(arrival_position_km.data, dtype=np.float64).reshape(3) * 1000.0
    v0_mps = np.asarray(departure.velocity_km_s.data, dtype=np.float64).reshape(3) * 1000.0

    v1t_mps, v2t_mps = _lambert_vallado(r0_m, r_m, tof_s, mu, prograde=prograde)

    dv1_mps = v1t_mps - v0_mps
    total_dv_mps = float(np.linalg.norm(dv1_mps))

    frame = departure.frame
    post_state = StateVector(
        position_km=Vector3(data=r_m / 1000.0),
        velocity_km_s=Vector3(data=v2t_mps / 1000.0),
        epoch=arrival_epoch,
        frame=frame,
    )

    maneuvers = [
        Maneuver(
            epoch=departure.epoch,
            delta_v=Vector3(data=dv1_mps),
            frame=BurnFrame.ECI,
            duration_s=0.0,
        ),
    ]

    return ManeuverPlan(
        sat_id=sat_id,
        maneuvers=maneuvers,
        total_delta_v_mps=total_dv_mps,
        total_fuel_kg=0.0,
        objective="lambert_intercept_single_impulse",
        predicted_post_state=post_state,
        generated_by=PlanOrigin.SOLVER,
        generated_at=Epoch(instant=departure.epoch.instant.astimezone(timezone.utc), scale=departure.epoch.scale),
        validation_results=[],
        time_of_flight_s=tof_s,
    )
