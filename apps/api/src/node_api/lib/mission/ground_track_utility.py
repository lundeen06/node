"""Nominal vs candidate TLE: parallel ground-track and ECI-position loss; utility and Δv coupling."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import numpy as np

from node_api.lib.geodesy import eci_m_to_lon_lat_deg, great_circle_distance_km
from node_api.lib.tle_physics import sgp4_position_eci_m
from node_api.types.mission_economics import (
    EciPositionDeviationReport,
    GroundTrackDeviationReport,
    OrbitDeviationPairReport,
    OrbitUtilityBreakdown,
)


def _linspace_utc(t0: datetime, t1: datetime, n: int) -> list[datetime]:
    if n < 1:
        msg = "n_samples must be at least 1."
        raise ValueError(msg)
    a = t0.astimezone(UTC)
    b = t1.astimezone(UTC)
    if b < a:
        msg = "t1_utc must be on or after t0_utc."
        raise ValueError(msg)
    if n == 1:
        return [a]
    span = (b - a).total_seconds()
    if span <= 0 and n > 1:
        msg = "t1_utc must be strictly after t0_utc when n_samples > 1."
        raise ValueError(msg)
    return [a + timedelta(seconds=span * i / (n - 1)) for i in range(n)]


def _stats_from_distances_km(d_km: list[float]) -> tuple[float, float, float, float, int]:
    n = len(d_km)
    mse = sum(x * x for x in d_km) / n
    mean_abs = sum(d_km) / n
    rmse = math.sqrt(mse)
    return rmse, mean_abs, max(d_km), mse, n


def _parallel_separations_km(
    baseline_line1: str,
    baseline_line2: str,
    candidate_line1: str,
    candidate_line2: str,
    times_utc: list[datetime],
) -> tuple[list[float], list[float]]:
    """Per time: great-circle subsatellite km, and 3D ECI position separation km (same TEME frame)."""
    gt: list[float] = []
    eci: list[float] = []
    for t in times_utc:
        tt = t.astimezone(UTC)
        r0 = sgp4_position_eci_m(baseline_line1, baseline_line2, tt)
        r1 = sgp4_position_eci_m(candidate_line1, candidate_line2, tt)
        diff = np.asarray(r0, dtype=np.float64) - np.asarray(r1, dtype=np.float64)
        eci.append(float(np.linalg.norm(diff)) / 1000.0)
        lon0, lat0 = eci_m_to_lon_lat_deg(r0, tt)
        lon1, lat1 = eci_m_to_lon_lat_deg(r1, tt)
        gt.append(great_circle_distance_km(lon0, lat0, lon1, lat1))
    return gt, eci


def ground_track_separations_km(
    baseline_line1: str,
    baseline_line2: str,
    candidate_line1: str,
    candidate_line2: str,
    times_utc: list[datetime],
) -> list[float]:
    """Great-circle distance between subsatellite points at each shared UTC time."""
    gt, _eci = _parallel_separations_km(
        baseline_line1,
        baseline_line2,
        candidate_line1,
        candidate_line2,
        times_utc,
    )
    return gt


def eci_position_separations_km(
    baseline_line1: str,
    baseline_line2: str,
    candidate_line1: str,
    candidate_line2: str,
    times_utc: list[datetime],
) -> list[float]:
    """‖r_nom − r_cand‖ (km) at each shared UTC time."""
    _gt, eci = _parallel_separations_km(
        baseline_line1,
        baseline_line2,
        candidate_line1,
        candidate_line2,
        times_utc,
    )
    return eci


def orbit_dual_deviation_report(
    baseline_line1: str,
    baseline_line2: str,
    candidate_line1: str,
    candidate_line2: str,
    t0_utc: datetime,
    t1_utc: datetime,
    *,
    n_samples: int = 48,
) -> OrbitDeviationPairReport:
    """RMSE / MSE for ground track and ECI position over ``[t0, t1]`` (single SGP4 pass per sample)."""
    times = _linspace_utc(t0_utc, t1_utc, n_samples)
    d_gt, d_eci = _parallel_separations_km(
        baseline_line1,
        baseline_line2,
        candidate_line1,
        candidate_line2,
        times,
    )
    g_rmse, g_mean, g_max, g_mse, gn = _stats_from_distances_km(d_gt)
    e_rmse, e_mean, e_max, e_mse, en = _stats_from_distances_km(d_eci)
    assert gn == en
    return OrbitDeviationPairReport(
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


def ground_track_deviation_report(
    baseline_line1: str,
    baseline_line2: str,
    candidate_line1: str,
    candidate_line2: str,
    t0_utc: datetime,
    t1_utc: datetime,
    *,
    n_samples: int = 48,
) -> GroundTrackDeviationReport:
    """RMSE / MSE of subsatellite-track separation over ``[t0, t1]`` (inclusive endpoints)."""
    return orbit_dual_deviation_report(
        baseline_line1,
        baseline_line2,
        candidate_line1,
        candidate_line2,
        t0_utc,
        t1_utc,
        n_samples=n_samples,
    ).ground_track


def eci_position_deviation_report(
    baseline_line1: str,
    baseline_line2: str,
    candidate_line1: str,
    candidate_line2: str,
    t0_utc: datetime,
    t1_utc: datetime,
    *,
    n_samples: int = 48,
) -> EciPositionDeviationReport:
    """RMSE of 3D SGP4 position separation (km) over ``[t0, t1]``."""
    return orbit_dual_deviation_report(
        baseline_line1,
        baseline_line2,
        candidate_line1,
        candidate_line2,
        t0_utc,
        t1_utc,
        n_samples=n_samples,
    ).eci_position


def utility_exponential_rmse(rmse_km: float, length_scale_km: float) -> float:
    """U = exp(−rmse / L); U=1 on the nominal track, falls toward 0 when far off."""
    if length_scale_km <= 0:
        msg = "length_scale_km must be positive."
        raise ValueError(msg)
    return float(math.exp(-max(0.0, rmse_km) / length_scale_km))


def track_opportunity_cost(rmse_km: float, length_scale_km: float) -> float:
    """−log(U) for :func:`utility_exponential_rmse`; grows linearly in RMSE for small deviations."""
    u = utility_exponential_rmse(rmse_km, length_scale_km)
    return float(-math.log(max(u, 1e-300)))


def combined_mission_loss(
    rmse_km: float,
    delta_v_used_mps: float,
    delta_v_budget_mps: float,
    *,
    length_scale_km: float = 25.0,
    w_track: float = 1.0,
    w_fuel: float = 1.0,
    fuel_denominator_mps: float | None = None,
    rmse_eci_km: float = 0.0,
    length_scale_eci_km: float = 5.0,
    w_eci: float = 1.0,
) -> float:
    """Track + optional ECI opportunity costs, plus quadratic fuel overrun penalty."""
    track = w_track * track_opportunity_cost(rmse_km, length_scale_km)
    eci = 0.0
    if w_eci != 0.0:
        eci = w_eci * track_opportunity_cost(rmse_eci_km, length_scale_eci_km)
    overrun = max(0.0, float(delta_v_used_mps) - float(delta_v_budget_mps))
    denom = float(delta_v_budget_mps) if fuel_denominator_mps is None else float(fuel_denominator_mps)
    if denom <= 0:
        msg = "delta_v_budget_mps (or fuel_denominator_mps) must be positive."
        raise ValueError(msg)
    fuel = w_fuel * (overrun / denom) ** 2
    return track + eci + fuel


def orbit_utility_breakdown_from_rmses(
    ground_track_rmse_km: float,
    eci_position_rmse_km: float,
    delta_v_used_mps: float,
    delta_v_budget_mps: float,
    *,
    length_scale_track_km: float = 25.0,
    length_scale_eci_km: float = 5.0,
    w_track: float = 1.0,
    w_eci: float = 1.0,
    w_fuel: float = 1.0,
) -> OrbitUtilityBreakdown:
    """Build :class:`OrbitUtilityBreakdown` from precomputed RMSEs (e.g. TLE–TLE or burn preview)."""
    u_g = utility_exponential_rmse(ground_track_rmse_km, length_scale_track_km)
    u_e = utility_exponential_rmse(eci_position_rmse_km, length_scale_eci_km)
    u = u_g * u_e
    toc_g = track_opportunity_cost(ground_track_rmse_km, length_scale_track_km)
    toc_e = track_opportunity_cost(eci_position_rmse_km, length_scale_eci_km)
    overrun = max(0.0, float(delta_v_used_mps) - float(delta_v_budget_mps))
    comb = combined_mission_loss(
        ground_track_rmse_km,
        delta_v_used_mps,
        delta_v_budget_mps,
        length_scale_km=length_scale_track_km,
        w_track=w_track,
        w_fuel=w_fuel,
        rmse_eci_km=eci_position_rmse_km,
        length_scale_eci_km=length_scale_eci_km,
        w_eci=w_eci,
    )
    return OrbitUtilityBreakdown(
        ground_track_rmse_km=ground_track_rmse_km,
        eci_position_rmse_km=eci_position_rmse_km,
        utility_ground_track_unitless=u_g,
        utility_eci_position_unitless=u_e,
        utility_unitless=u,
        track_opportunity_cost=toc_g,
        eci_opportunity_cost=toc_e,
        delta_v_used_mps=float(delta_v_used_mps),
        delta_v_budget_mps=float(delta_v_budget_mps),
        fuel_overrun_mps=overrun,
        combined_loss=comb,
    )


def orbit_utility_breakdown(
    baseline_line1: str,
    baseline_line2: str,
    candidate_line1: str,
    candidate_line2: str,
    t0_utc: datetime,
    t1_utc: datetime,
    *,
    delta_v_used_mps: float,
    delta_v_budget_mps: float,
    n_samples: int = 48,
    length_scale_track_km: float = 25.0,
    length_scale_eci_km: float = 5.0,
    w_track: float = 1.0,
    w_eci: float = 1.0,
    w_fuel: float = 1.0,
) -> OrbitUtilityBreakdown:
    """Ground-track + ECI tube deviation vs nominal TLE, product utility, and budget-weighted loss."""
    dual = orbit_dual_deviation_report(
        baseline_line1,
        baseline_line2,
        candidate_line1,
        candidate_line2,
        t0_utc,
        t1_utc,
        n_samples=n_samples,
    )
    return orbit_utility_breakdown_from_rmses(
        dual.ground_track.rmse_km,
        dual.eci_position.rmse_km,
        delta_v_used_mps,
        delta_v_budget_mps,
        length_scale_track_km=length_scale_track_km,
        length_scale_eci_km=length_scale_eci_km,
        w_track=w_track,
        w_eci=w_eci,
        w_fuel=w_fuel,
    )
