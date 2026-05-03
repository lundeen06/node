"""Collision avoidance using the two-body Lambert solver for impulsive geometry."""

from __future__ import annotations

from datetime import UTC, timedelta

import math
import numpy as np
from numpy.typing import NDArray

from node_api.errors import InfeasibleProblemError
from node_api.lib.solvers.lambert import solve_lambert_problem
from node_api.lib.tle_physics import trajectory_states_sgp4
from node_api.physics_runtime import ensure_physics_importable
from node_api.types.common import Vector3
from node_api.types.conjunction import CloseApproach
from node_api.types.constellation import HouseRules
from node_api.types.maneuver import BurnFrame, Maneuver, ManeuverPlan, PlanOrigin, ValidationOutcome
from node_api.types.satellite import SatelliteState
from node_api.types.state import StateVector
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
    try:
        oe0 = util_dyn.pv_to_oe(pv, mu)
        a_m = float(oe0[0])
        if not math.isfinite(a_m) or a_m <= 0.0:
            msg = "Two-body coast: PV implies non-positive semi-major axis (non-Keplerian or hyperbolic); cannot propagate."
            raise InfeasibleProblemError(msg)
        oe1 = util_dyn.propagate_oe(oe0, float(dt_s), mu=mu, J2=0.0)
        out = np.asarray(util_dyn.oe_to_pv(oe1, mu), dtype=np.float64).reshape(6)
    except InfeasibleProblemError:
        raise
    except (ValueError, AssertionError, RuntimeError, OverflowError) as exc:
        raise InfeasibleProblemError(f"Two-body coast from PV failed: {exc}") from exc
    r_out = out[0:3] / 1000.0
    v_out = out[3:6] / 1000.0
    if not np.all(np.isfinite(np.concatenate([r_out, v_out]))):
        msg = "Two-body coast produced non-finite position/velocity (check orbit energy / timestep)."
        raise InfeasibleProblemError(msg)
    return r_out, v_out


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


def _angular_momentum_unit(r_km: NDArray[np.float64], v_km_s: NDArray[np.float64]) -> NDArray[np.float64]:
    """Normalized :math:`\\widehat{r\\times v}` (along-track singularities fall back to radial normal)."""
    r = np.asarray(r_km, dtype=np.float64).reshape(3)
    v = np.asarray(v_km_s, dtype=np.float64).reshape(3)
    h = np.cross(r, v)
    hn = float(np.linalg.norm(h))
    if hn < 1e-12:
        rn = float(np.linalg.norm(r))
        if rn < 1e-12:
            msg = "Position/velocity degenerate; cannot form orbit normal."
            raise InfeasibleProblemError(msg)
        er = r / rn
        aux = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        proj = aux - np.dot(aux, er) * er
        pn = float(np.linalg.norm(proj))
        if pn < 1e-12:
            aux = np.array([0.0, 1.0, 0.0], dtype=np.float64)
            proj = aux - np.dot(aux, er) * er
            pn = float(np.linalg.norm(proj))
        if pn < 1e-14:
            msg = "Cannot build a finite cross-track direction from state."
            raise InfeasibleProblemError(msg)
        return proj / pn
    return h / hn


def _cross_track_fallback_plan(
    ego: SatelliteState,
    *,
    maneuver_epoch: Epoch,
    arrival_epoch: Epoch,
    departure: StateVector,
    r_tc_nominal_km: NDArray[np.float64],
    v_tc_nominal_km_s: NDArray[np.float64],
    dt_s: float,
    max_delta_v_mps: float,
    pc_target: float,
    threat: CloseApproach,
    burn_lead_s: float,
    extra_bias_km: float,
) -> ManeuverPlan:
    """Single impulsive Δv along :math:`\\hat h` at burn; magnitude from a coarse grid under ``max_delta_v_mps``.

    Used when Lambert to a fixed TCA offset fails (singular chord, Δv bound, numerical issues). Separation is
    scored by projecting the coasted TCA position (after the impulse) minus the nominal coast onto the TCA
    orbit normal — same normal family as deterministic avoidance offsets. Exploratory only; **Pc is not recomputed** (``pc_target`` is policy context only).
    """
    r0 = np.asarray(departure.position_km.data, dtype=np.float64).reshape(3)
    v0 = np.asarray(departure.velocity_km_s.data, dtype=np.float64).reshape(3)

    u_burn = _angular_momentum_unit(r0, v0)
    u_tca = _angular_momentum_unit(r_tc_nominal_km, v_tc_nominal_km_s)

    target_sep_mag_km = max(0.1, float(extra_bias_km) + max(0.0, threat.miss_distance_km) * 0.2)

    n_steps = min(56, max(24, int(max_delta_v_mps / 50.0) + 8))
    best_pick: tuple[float, float, float, NDArray[np.float64], NDArray[np.float64]] | None = None

    for sign_dir in (1.0, -1.0):
        for i in range(1, n_steps + 1):
            alpha_mps = max_delta_v_mps * (i / float(n_steps))
            dv_km_s = sign_dir * (alpha_mps / 1000.0) * u_burn
            v_apply = v0 + dv_km_s
            try:
                r_hit, v_hit = _propagate_two_body_cartesian_km(r0, v_apply, dt_s)
                mag = abs(float(np.dot(r_hit - r_tc_nominal_km, u_tca)))
            except (InfeasibleProblemError, OverflowError, ValueError):
                continue
            if not math.isfinite(mag):
                continue
            if best_pick is None:
                best_pick = (alpha_mps, sign_dir, mag, r_hit, v_hit)
                continue
            prev_alpha, prev_sign, prev_mag, _, _ = best_pick
            if mag > prev_mag + 1e-15:
                best_pick = (alpha_mps, sign_dir, mag, r_hit, v_hit)
            elif abs(mag - prev_mag) < 1e-12 and alpha_mps < prev_alpha - 1e-12:
                best_pick = (alpha_mps, sign_dir, mag, r_hit, v_hit)

    if best_pick is None or best_pick[0] <= 1e-9:
        raise InfeasibleProblemError(
            "Cross-track fallback could not sweep a nonzero Δv under the Δv budget.",
        )
    alpha_use, sign_use, sep_mag_km, r_post, v_post = best_pick
    if sep_mag_km < 1e-5:
        raise InfeasibleProblemError(
            "Cross-track fallback produced negligible predicted TCA separation (~<10 m projected); chord geometry likely degenerate.",
        )

    dv_mps_vec = sign_use * alpha_use * u_burn
    maneuver = Maneuver(
        epoch=maneuver_epoch,
        delta_v=Vector3(data=np.asarray(dv_mps_vec, dtype=np.float64).reshape(3)),
        frame=BurnFrame.ECI,
        duration_s=0.0,
    )

    post_state = StateVector(
        position_km=Vector3(data=r_post),
        velocity_km_s=Vector3(data=v_post),
        epoch=arrival_epoch,
        frame=departure.frame,
    )

    note = ValidationOutcome(
        check_id="cross_track_fallback_impulse",
        passed=True,
        message=(
            f"Fallback ‖Δv‖ = {alpha_use:.3f} m/s along burn-time orbit normal (Lambert chord infeasible or bound). "
            f"Rough |projected cross-track shift| at TCA ≈ {sep_mag_km:.3f} km vs nominal coast-heuristic "
            f"{target_sep_mag_km:.1f} km; burn lead {burn_lead_s:g} s; P_c policy gate ({pc_target:g}) not recomputed "
            "(re-screen with catalog tool after committing an ephemeris change)."
        ),
    )
    return ManeuverPlan(
        sat_id=ego.sat_id,
        maneuvers=[maneuver],
        total_delta_v_mps=float(alpha_use),
        total_fuel_kg=0.0,
        objective="cross_track_fallback_collision_avoidance_single_impulse",
        predicted_post_state=post_state,
        generated_by=PlanOrigin.SOLVER,
        generated_at=Epoch(instant=maneuver_epoch.as_utc_datetime().astimezone(UTC), scale=TimeScale.UTC),
        validation_results=[note],
        time_of_flight_s=float(dt_s),
    )


def _departure_state_at_burn(
    ego: SatelliteState,
    maneuver_epoch: Epoch,
    line1: str,
    line2: str,
) -> StateVector:
    """PV at the burn epoch from SGP4 (catalog TLE); frame matches ``ego``."""
    t = maneuver_epoch.as_utc_datetime().astimezone(UTC)
    _tt, r_km, v_km_s = trajectory_states_sgp4(line1, line2, [t])[0]
    return StateVector(
        position_km=Vector3(data=np.asarray(r_km, dtype=np.float64)),
        velocity_km_s=Vector3(data=np.asarray(v_km_s, dtype=np.float64)),
        epoch=maneuver_epoch,
        frame=ego.state_vector.frame,
    )


def _solve_impulsive_avoidance_with_lead(
    ego: SatelliteState,
    threat: CloseApproach,
    max_delta_v_mps: float,
    pc_target: float,
    *,
    burn_lead_s: float,
    extra_separation_km: float,
    tle_line1: str | None = None,
    tle_line2: str | None = None,
) -> ManeuverPlan:
    if max_delta_v_mps <= 0:
        msg = "max_delta_v_mps must be positive."
        raise InfeasibleProblemError(msg)

    t_tca = threat.tca.as_utc_datetime()
    t_ego = ego.state_vector.epoch.as_utc_datetime()
    # Lambert needs strictly positive time-of-flight; allow "immediate" burns (lead 0) with a 1 ms coast.
    min_tof_s = 1e-3
    lead_s = float(burn_lead_s)
    eff_lead_s = min_tof_s if lead_s <= 0.0 else max(lead_s, min_tof_s)
    t_preferred_burn = t_tca - timedelta(seconds=eff_lead_s)
    dep_instant = max(t_ego, t_preferred_burn)
    tof_remaining_s = (t_tca - dep_instant).total_seconds()
    if tof_remaining_s < min_tof_s:
        msg = (
            f"Insufficient time before TCA for a Lambert leg (need > {min_tof_s:g} s coast; "
            f"got {tof_remaining_s:g} s)."
        )
        raise InfeasibleProblemError(msg)

    maneuver_epoch = Epoch(instant=dep_instant.astimezone(UTC), scale=TimeScale.UTC)
    arrival_epoch = threat.tca

    if tle_line1 and tle_line2:
        departure = _departure_state_at_burn(ego, maneuver_epoch, tle_line1, tle_line2)
    else:
        r_now = np.asarray(ego.state_vector.position_km.data, dtype=np.float64).reshape(3)
        v_now = np.asarray(ego.state_vector.velocity_km_s.data, dtype=np.float64).reshape(3)
        dt_to_burn_s = (maneuver_epoch.as_utc_datetime() - ego.state_vector.epoch.as_utc_datetime()).total_seconds()
        r0_prop, v0_prop = _propagate_two_body_cartesian_km(r_now, v_now, dt_to_burn_s)
        departure = ego.state_vector.model_copy(
            update={
                "position_km": Vector3(data=r0_prop),
                "velocity_km_s": Vector3(data=v0_prop),
                "epoch": maneuver_epoch,
            },
        )
    r0 = np.asarray(departure.position_km.data, dtype=np.float64).reshape(3)
    v0 = np.asarray(departure.velocity_km_s.data, dtype=np.float64).reshape(3)

    dt_s = (arrival_epoch.as_utc_datetime() - maneuver_epoch.as_utc_datetime()).total_seconds()
    r_tc_km, v_tc_km_s = _propagate_two_body_cartesian_km(r0, v0, dt_s)

    extra = float(extra_separation_km)
    plan: ManeuverPlan | None = None
    extra_used = extra
    last_extra_tried = extra
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
            last_extra_tried = extra
            extra *= 0.72
            continue
        if candidate.total_delta_v_mps <= max_delta_v_mps:
            plan = candidate
            extra_used = extra
            break
        last_extra_tried = extra
        extra *= 0.72

    lambert_context = ""
    if plan is None:
        lambert_context = (
            f"Lambert iterations exhausted (last nominal separation bias ≈ {last_extra_tried:.2f} km) "
            f"within ‖Δv‖ ≤ {max_delta_v_mps:g} m/s; trying cross-track impulse grid."
        )
        try:
            plan = _cross_track_fallback_plan(
                ego,
                maneuver_epoch=maneuver_epoch,
                arrival_epoch=arrival_epoch,
                departure=departure,
                r_tc_nominal_km=r_tc_km,
                v_tc_nominal_km_s=v_tc_km_s,
                dt_s=dt_s,
                max_delta_v_mps=max_delta_v_mps,
                pc_target=pc_target,
                threat=threat,
                burn_lead_s=burn_lead_s,
                extra_bias_km=max(10.0, last_extra_tried),
            )
        except InfeasibleProblemError:
            plan = None

    if plan is None:
        msg = f"No collision-avoidance maneuver within ‖Δv‖ ≤ {max_delta_v_mps:g} m/s (Lambert + cross-track fallback both failed)."
        if lambert_context:
            msg = f"{msg} {lambert_context}"
        raise InfeasibleProblemError(msg)

    if plan.objective == "cross_track_fallback_collision_avoidance_single_impulse":
        skip = ValidationOutcome(
            check_id="lambert_primary_skipped",
            passed=True,
            message=lambert_context or "Lambert avoidance chord unavailable; emitted cross-track impulse fallback.",
        )
        return plan.model_copy(
            update={"validation_results": [*plan.validation_results, skip]},
        )

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
    tle_line1: str | None = None,
    tle_line2: str | None = None,
) -> ManeuverPlan:
    """Lambert single-impulse leg from a pre-TCA burn to an out-of-plane miss at TCA.

    Departure epoch is ``max(ego.state_vector.epoch, TCA − effective_lead)`` where
    ``effective_lead`` is ``burn_lead_s`` (minimum 1 ms) or, when ``burn_lead_s <= 0``,
    a 1 ms coast so Lambert has positive time-of-flight.     Cartesian PV at departure uses
    two-body propagation from ``ego`` unless TLE lines are passed. Nominal TCA
    location is a J2=0 two-body coast from that PV; the arrival target offsets that
    position along :math:`\\hat h` until total Δv fits ``max_delta_v_mps``.
    When those Lambert iterations exhaust the budget without a chord, an automatic
    cross-track impulse fallback is synthesized under the same ‖Δv‖ cap before failing.
    """
    return _solve_impulsive_avoidance_with_lead(
        ego,
        threat,
        max_delta_v_mps,
        pc_target,
        burn_lead_s=burn_lead_s,
        extra_separation_km=extra_separation_km,
        tle_line1=tle_line1,
        tle_line2=tle_line2,
    )


def solve_optimal_avoidance_timing(
    ego: SatelliteState,
    threat: CloseApproach,
    house_rules: HouseRules,
    *,
    tle_line1: str | None = None,
    tle_line2: str | None = None,
) -> ManeuverPlan:
    """Try several pre-TCA burn leads; return the feasible plan with lowest total Δv."""
    leads = (0.0, 60.0, 300.0, 600.0, 1200.0, 2400.0, 4800.0, 7200.0, 9600.0, 21600.0, 86400.0)
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
                tle_line1=tle_line1,
                tle_line2=tle_line2,
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
        message=(
            "Chose pre-TCA burn lead (scan from immediate through +24 h) minimizing ‖Δv‖; each lead tries Lambert "
            "avoidance first, then a cross-track impulse grid if the Lambert chord is infeasible."
        ),
    )
    return best.model_copy(update={"validation_results": [*best.validation_results, note]})
