"""Burn utility: ideal no-maneuver ephemeris (SGP4) vs post-maneuver propagated path over one orbit."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import numpy as np
from numpy.typing import NDArray

from node_api.lib.geodesy import eci_m_to_lon_lat_deg, great_circle_distance_km
from node_api.lib.mission.ground_track_utility import (
    _linspace_utc,
    _stats_from_distances_km,
    orbit_utility_breakdown_from_rmses,
)
from node_api.lib.solvers.avoidance import _propagate_two_body_cartesian_km
from node_api.lib.tle_physics import sgp4_position_eci_m, trajectory_states_sgp4, tle_orbital_period_kozai_s
from node_api.types.maneuver import BurnFrame, Maneuver
from node_api.types.mission_economics import EciPositionDeviationReport, GroundTrackDeviationReport, OrbitDeviationPairReport

# Impulsive position is continuous; skip the degenerate instant so RMSE reflects a departed trajectory.
_POST_BURN_GRID_START_EPS_S = 1.0


def _r_post_maneuver_m(
    line1: str,
    line2: str,
    imp_sorted: list[tuple[datetime, NDArray[np.float64]]],
    t_q: datetime,
) -> NDArray[np.float64]:
    """If you execute the plan: SGP4 before first burn; after, impulsive ECI Δvs + J2=0 two-body coast. m."""
    t_q = t_q.astimezone(UTC)
    t_first = imp_sorted[0][0]
    if t_q < t_first:
        return np.asarray(sgp4_position_eci_m(line1, line2, t_q), dtype=np.float64).reshape(3)

    _tt0, r_km, v_km_s = trajectory_states_sgp4(line1, line2, [t_first])[0]
    r = np.asarray(r_km, dtype=np.float64).reshape(3)
    v = np.asarray(v_km_s, dtype=np.float64).reshape(3) + imp_sorted[0][1] / 1000.0
    t_cursor = t_first

    for idx in range(1, len(imp_sorted)):
        t_next, dv_next = imp_sorted[idx]
        if t_q < t_next:
            dt_s = (t_q - t_cursor).total_seconds()
            rk, _vk = _propagate_two_body_cartesian_km(r, v, float(dt_s))
            return np.asarray(rk, dtype=np.float64).reshape(3) * 1000.0
        dt_s = (t_next - t_cursor).total_seconds()
        r, v = _propagate_two_body_cartesian_km(r, v, float(dt_s))
        v = np.asarray(v, dtype=np.float64).reshape(3) + dv_next / 1000.0
        t_cursor = t_next

    dt_s = (t_q - t_cursor).total_seconds()
    rk, _vk = _propagate_two_body_cartesian_km(r, v, float(dt_s))
    return np.asarray(rk, dtype=np.float64).reshape(3) * 1000.0


def _verdict_ratio(ratio: float) -> str:
    if ratio < 0.2:
        return "small"
    if ratio < 1.0:
        return "moderate"
    return "large"


def preview_plan_utility_vs_catalog_tle(
    tle_line1: str,
    tle_line2: str,
    maneuvers: Sequence[Maneuver],
    *,
    n_samples: int = 48,
    delta_v_budget_mps: float,
    delta_v_used_mps: float | None = None,
    length_scale_track_km: float = 25.0,
    length_scale_eci_km: float = 5.0,
    w_track: float = 1.0,
    w_eci: float = 1.0,
    w_fuel: float = 1.0,
    t0_utc: datetime | None = None,
    t1_utc: datetime | None = None,
    ideal_tle_line1: str | None = None,
    ideal_tle_line2: str | None = None,
) -> dict[str, object]:
    """Ideal **no-maneuver** path (SGP4 on mission / catalog TLE) vs **post-maneuver** hybrid path.

    - **Ideal (no burn)**: SGP4(``ideal_tle_*``) at each sample — defaults to the same lines as the catalog
      TLE when ``ideal_tle_*`` are omitted (frozen mission baseline can be wired in later).
    - **With maneuver(s)**: SGP4 before the first burn; from that epoch, apply ECI impulses and J2=0
      two-body coast (short-horizon proxy until a post-burn TLE exists).

    Default time grid is **strictly after** the first burn (starts ``t_first + 1 s``) through one Kozai
    period, so RMSE is not diluted by the impulse instant where positions match by construction.
    """
    if not maneuvers:
        return {"error": "No maneuvers in plan; cannot preview utility."}
    for m in maneuvers:
        if m.frame != BurnFrame.ECI:
            return {
                "error": "Utility preview supports ECI-frame maneuvers only.",
                "frame_seen": m.frame.value,
            }

    imp_sorted = sorted(
        (
            (m.epoch.as_utc_datetime().astimezone(UTC), np.asarray(m.delta_v.data, dtype=np.float64).reshape(3))
            for m in maneuvers
        ),
        key=lambda x: x[0],
    )
    t_first = imp_sorted[0][0]
    period_s = float(tle_orbital_period_kozai_s(tle_line1, tle_line2))
    ideal1 = ideal_tle_line1 or tle_line1
    ideal2 = ideal_tle_line2 or tle_line2

    eps = _POST_BURN_GRID_START_EPS_S
    if t0_utc is not None and t1_utc is not None:
        t0 = max(t0_utc.astimezone(UTC), t_first + timedelta(seconds=eps))
        t1 = t1_utc.astimezone(UTC)
        if t1 <= t0:
            return {
                "error": "t1_utc must be strictly after max(t0_utc, first_burn + 1s).",
                "first_burn_utc": t_first.isoformat().replace("+00:00", "Z"),
            }
    else:
        t0 = t_first + timedelta(seconds=eps)
        t1 = t_first + timedelta(seconds=period_s)
        if t1 <= t0:
            t1 = t0 + timedelta(seconds=max(60.0, 0.01 * period_s))

    ns = max(2, min(int(n_samples), 400))
    times = _linspace_utc(t0, t1, ns)
    d_gt: list[float] = []
    d_eci: list[float] = []
    for t in times:
        tt = t.astimezone(UTC)
        r_ideal_m = np.asarray(sgp4_position_eci_m(ideal1, ideal2, tt), dtype=np.float64).reshape(3)
        r_post_mnv_m = _r_post_maneuver_m(tle_line1, tle_line2, imp_sorted, tt)
        d_eci.append(float(np.linalg.norm(r_ideal_m - r_post_mnv_m)) / 1000.0)
        lon0, lat0 = eci_m_to_lon_lat_deg(r_ideal_m, tt)
        lon1, lat1 = eci_m_to_lon_lat_deg(r_post_mnv_m, tt)
        d_gt.append(great_circle_distance_km(lon0, lat0, lon1, lat1))

    sum_gt_km2 = float(sum(x * x for x in d_gt))
    sum_eci_km2 = float(sum(x * x for x in d_eci))

    g_rmse, g_mean, g_max, g_mse, gn = _stats_from_distances_km(d_gt)
    e_rmse, e_mean, e_max, e_mse, en = _stats_from_distances_km(d_eci)
    assert gn == en

    dual = OrbitDeviationPairReport(
        ground_track=GroundTrackDeviationReport(
            rmse_km=g_rmse,
            mean_abs_km=g_mean,
            max_km=g_max,
            mse_km2=g_mse,
            n_samples=gn,
        ),
        eci_position=EciPositionDeviationReport(
            rmse_km=e_rmse,
            mean_abs_km=e_mean,
            max_km=e_max,
            mse_km2=e_mse,
            n_samples=en,
        ),
    )
    if delta_v_used_mps is None:
        dv_used = float(
            sum(float(np.linalg.norm(np.asarray(m.delta_v.data, dtype=np.float64))) for m in maneuvers),
        )
    else:
        dv_used = float(delta_v_used_mps)
    budget = max(float(delta_v_budget_mps), 1e-6)
    util = orbit_utility_breakdown_from_rmses(
        dual.ground_track.rmse_km,
        dual.eci_position.rmse_km,
        dv_used,
        budget,
        length_scale_track_km=length_scale_track_km,
        length_scale_eci_km=length_scale_eci_km,
        w_track=w_track,
        w_eci=w_eci,
        w_fuel=w_fuel,
    )

    rt = g_rmse / max(length_scale_track_km, 1e-9)
    re = e_rmse / max(length_scale_eci_km, 1e-9)

    uses_mission_ideal = bool(ideal_tle_line1 and ideal_tle_line2)

    return {
        "preview_method": "post_maneuver_coast_vs_ideal_sgp4_no_maneuver_over_one_orbit",
        "t0_utc": t0.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "t1_utc": t1.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "first_burn_utc": t_first.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "orbital_period_s": period_s,
        "n_samples": gn,
        "sampling_note": (
            f"RMSE and integrated_loss use UTC samples in [t0, t1] with t0 ≥ first_burn + {eps:g} s so "
            "metrics reflect separation after the impulse (position is continuous across an impulsive burn)."
        ),
        "ideal_ephemeris": "mission_tle" if uses_mission_ideal else "catalog_tle_same_as_current_row",
        "integrated_loss": {
            "ground_track_sum_squared_separation_km2": sum_gt_km2,
            "eci_position_sum_squared_separation_km2": sum_eci_km2,
            "sum_squared_total_km2": sum_gt_km2 + sum_eci_km2,
            "note": (
                "Discrete Σ‖Δ‖² over the preview lattice. Comparable across plans with the same n_samples."
            ),
        },
        "calibration": {
            "length_scale_track_km": float(length_scale_track_km),
            "length_scale_eci_km": float(length_scale_eci_km),
            "rmse_track_ratio_to_length_scale": float(rt),
            "rmse_eci_ratio_to_length_scale": float(re),
            "verdict_ground_track": _verdict_ratio(rt),
            "verdict_eci": _verdict_ratio(re),
            "how_to_read": (
                "RMSE is root-mean pointwise separation (km). Ratios divide RMSE by the exp-kernel length L: "
                "below ~0.2 is small relative to policy, near or above 1 is large. Verdicts mirror that. "
                "Utility exp(-RMSE/L) uses the same L values as in evaluate_orbit_mission_value defaults."
            ),
        },
        "parallel_deviation": dual.model_dump(),
        "utility_and_loss": util.model_dump(),
        "interpretation": (
            "Ideal path = SGP4 on the ideal TLE (defaults to catalog: the orbit if you never maneuver). "
            "Actual path = catalog SGP4 before the first burn, then planned impulses + J2=0 two-body coast. "
            "When ideal lines match the catalog, differences are maneuver + propagator mismatch vs SGP4; "
            "pass distinct ideal_tle_* when you freeze a mission baseline. For strict TLE-vs-TLE deltas, "
            "use evaluate_orbit_mission_value."
        ),
    }
