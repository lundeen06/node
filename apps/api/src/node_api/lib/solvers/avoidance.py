"""Collision avoidance using the two-body Lambert solver for impulsive geometry."""

from __future__ import annotations

from datetime import UTC, timedelta

import numpy as np
from numpy.typing import NDArray

from node_api.errors import InfeasibleProblemError
from node_api.lib.solvers.lambert import solve_lambert_problem
from node_api.physics_runtime import ensure_physics_importable
from node_api.types.common import Vector3
from node_api.types.conjunction import CloseApproach
from node_api.types.constellation import HouseRules
from node_api.types.maneuver import ManeuverPlan, PlanOrigin, ValidationOutcome
from node_api.types.satellite import SatelliteState
from node_api.types.time import Epoch, TimeScale

ensure_physics_importable()
from physics.propulsion import util_dyn  # noqa: E402


def _propagate_two_body_cartesian_km(
    r_km: NDArray[np.float64],
    v_km_s: NDArray[np.float64],
    dt_s: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Coast Cartesian PV (km, km/s) for ``dt_s`` seconds under J2=0 mean-element flow."""
    r = np.asarray(r_km, dtype=np.float64).reshape(3)
    v = np.asarray(v_km_s, dtype=np.float64).reshape(3)
    pv = np.concatenate([r * 1000.0, v * 1000.0])
    mu = float(util_dyn.mu_E)
    oe0 = util_dyn.pv_to_oe(pv, mu)
    oe1 = util_dyn.propagate_oe(oe0, float(dt_s), mu=mu, J2=0.0)
    out = np.asarray(util_dyn.oe_to_pv(oe1, mu), dtype=np.float64).reshape(6)
    return out[0:3] / 1000.0, out[3:6] / 1000.0


def _arrival_position_km_out_of_plane(
    r_km: NDArray[np.float64],
    v_km_s: NDArray[np.float64],
    *,
    miss_distance_km: float,
    extra_separation_km: float,
) -> NDArray[np.float64]:
    """Return a target position (km, ECI) offset from nominal ``r_km`` along :math:`\\hat h = r\\times v`."""
    r = np.asarray(r_km, dtype=np.float64).reshape(3)
    v = np.asarray(v_km_s, dtype=np.float64).reshape(3)
    h = np.cross(r, v)
    hn = float(np.linalg.norm(h))
    if hn < 1e-12:
        rn = float(np.linalg.norm(r))
        if rn < 1e-12:
            msg = "Ego position/velocity degenerate; cannot build avoidance offset."
            raise InfeasibleProblemError(msg)
        u = r / rn
    else:
        u = h / hn
    step = max(0.0, float(miss_distance_km)) * 0.5 + float(extra_separation_km)
    return r + u * step


def _solve_impulsive_avoidance_with_lead(
    ego: SatelliteState,
    threat: CloseApproach,
    max_delta_v_mps: float,
    pc_target: float,
    *,
    burn_lead_s: float,
    extra_separation_km: float,
) -> ManeuverPlan:
    if max_delta_v_mps <= 0:
        msg = "max_delta_v_mps must be positive."
        raise InfeasibleProblemError(msg)

    t_tca = threat.tca.as_utc_datetime()
    t_ego = ego.state_vector.epoch.as_utc_datetime()
    t_preferred_burn = t_tca - timedelta(seconds=float(burn_lead_s))
    dep_instant = max(t_ego, t_preferred_burn)
    if dep_instant >= t_tca - timedelta(seconds=16.0):
        msg = "Insufficient time before TCA for a Lambert avoidance leg."
        raise InfeasibleProblemError(msg)

    maneuver_epoch = Epoch(instant=dep_instant.astimezone(UTC), scale=TimeScale.UTC)
    arrival_epoch = threat.tca

    # Propagate ego to the chosen burn epoch before solving Lambert so departure
    # state and departure time are physically consistent.
    r_now = np.asarray(ego.state_vector.position_km.data, dtype=np.float64).reshape(3)
    v_now = np.asarray(ego.state_vector.velocity_km_s.data, dtype=np.float64).reshape(3)
    dt_to_burn_s = (maneuver_epoch.as_utc_datetime() - ego.state_vector.epoch.as_utc_datetime()).total_seconds()
    r0, v0 = _propagate_two_body_cartesian_km(r_now, v_now, dt_to_burn_s)
    departure = ego.state_vector.model_copy(
        update={
            "position_km": Vector3(data=r0),
            "velocity_km_s": Vector3(data=v0),
            "epoch": maneuver_epoch,
        },
    )

    dt_s = (arrival_epoch.as_utc_datetime() - maneuver_epoch.as_utc_datetime()).total_seconds()
    r_tc_km, v_tc_km_s = _propagate_two_body_cartesian_km(r0, v0, dt_s)

    extra = float(extra_separation_km)
    plan: ManeuverPlan | None = None
    extra_used = extra
    for _ in range(18):
        r_arr = _arrival_position_km_out_of_plane(
            r_tc_km,
            v_tc_km_s,
            miss_distance_km=threat.miss_distance_km,
            extra_separation_km=extra,
        )
        try:
            candidate = solve_lambert_problem(
                departure,
                Vector3(data=r_arr),
                arrival_epoch,
                prograde=True,
                sat_id=ego.sat_id,
            )
        except InfeasibleProblemError:
            extra *= 0.72
            continue
        if candidate.total_delta_v_mps <= max_delta_v_mps:
            plan = candidate
            extra_used = extra
            break
        extra *= 0.72

    if plan is None:
        msg = f"No Lambert avoidance within max Δv = {max_delta_v_mps:g} m/s (try larger lead time or policy limits)."
        raise InfeasibleProblemError(msg)

    note = (
        f"Single-impulse Lambert to out-of-plane offset from two-body coast at TCA; Pc gate {pc_target:g} not recomputed. "
        f"Burn lead {burn_lead_s:g} s before TCA; separation bias {extra_used:.1f} km."
    )
    val = ValidationOutcome(check_id="lambert_avoidance_geometry", passed=True, message=note)
    merged = plan.model_copy(
        update={
            "objective": "lambert_collision_avoidance_single_impulse",
            "validation_results": [*plan.validation_results, val],
            "generated_by": PlanOrigin.SOLVER,
        },
    )
    return merged


def solve_impulsive_avoidance(
    ego: SatelliteState,
    threat: CloseApproach,
    max_delta_v_mps: float,
    pc_target: float,
    *,
    burn_lead_s: float = 600.0,
    extra_separation_km: float = 40.0,
) -> ManeuverPlan:
    """Lambert single-impulse leg from a pre-TCA burn to an out-of-plane miss at TCA.

    Departure epoch is ``max(ego.state_vector.epoch, TCA − burn_lead_s)`` with the same
    Cartesian PV as ``ego`` (no fit-to-epoch propagation before the burn). Nominal TCA
    location is a J2=0 two-body coast from that PV; the arrival target offsets that
    position along :math:`\\hat h` until total Δv fits ``max_delta_v_mps``.
    """
    return _solve_impulsive_avoidance_with_lead(
        ego,
        threat,
        max_delta_v_mps,
        pc_target,
        burn_lead_s=burn_lead_s,
        extra_separation_km=extra_separation_km,
    )


def solve_optimal_avoidance_timing(
    ego: SatelliteState,
    threat: CloseApproach,
    house_rules: HouseRules,
) -> ManeuverPlan:
    """Try several pre-TCA burn leads; return the feasible plan with lowest total Δv."""
    leads = (300.0, 600.0, 1200.0, 2400.0, 4800.0)
    best: ManeuverPlan | None = None
    last_err: InfeasibleProblemError | None = None
    for lead in leads:
        try:
            p = _solve_impulsive_avoidance_with_lead(
                ego,
                threat,
                house_rules.max_auto_delta_v_mps,
                house_rules.pc_mitigation_threshold,
                burn_lead_s=lead,
                extra_separation_km=40.0,
            )
        except InfeasibleProblemError as exc:
            last_err = exc
            continue
        if best is None or p.total_delta_v_mps < best.total_delta_v_mps:
            best = p
    if best is None:
        msg = "No feasible Lambert avoidance timing in the searched burn-lead window."
        if last_err is not None:
            msg = f"{msg} Last detail: {last_err}"
        raise InfeasibleProblemError(msg)
    note = ValidationOutcome(
        check_id="timing_search",
        passed=True,
        message="Chose burn lead among {300,600,1200,2400,4800}s before TCA with minimum total Δv.",
    )
    return best.model_copy(update={"validation_results": [*best.validation_results, note]})
