"""Pairwise SGP4 screening: 1 km keep-out sphere and encounter statistics.

Uses the ``sgp4`` library to evaluate both TLEs on a shared time grid (vectorized
distance) for efficiency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
from sgp4.api import WGS72, Satrec
from sgp4.conveniences import jday_datetime


@dataclass(frozen=True, slots=True)
class PairSphereScreenResult:
    """Outcome of :func:`screen_pair_sphere_sgp4`."""

    conjunction_occurred: bool
    closest_approach_km: float
    first_entry_utc: datetime | None
    my_orbital_period_s: float
    time_points_inside_sphere: int
    total_time_points: int
    time_spent_inside_s: float
    integration_start_utc: datetime
    integration_end_utc: datetime
    step_s: float
    sphere_radius_km: float
    probability_heuristic: float
    weight_distance: float
    weight_time: float


def _period_s_from_tle(line1: str, line2: str) -> float:
    """Orbital period from SGP4 Kozai mean motion (rad/min)."""
    sat = Satrec.twoline2rv(line1, line2, WGS72)
    nm = float(sat.no_kozai)  # rad/min
    if nm <= 0:
        msg = "TLE has invalid mean motion (no_kozai <= 0)."
        raise ValueError(msg)
    return 2.0 * math.pi * 60.0 / nm


def _position_km(sat: Satrec, t: datetime) -> np.ndarray:
    """ECI position (km) for one object at one instant; reuses a built :class:`Satrec`."""
    jd, fr = jday_datetime(t.astimezone(UTC))
    err, r_km, _v = sat.sgp4(jd, fr)
    if err != 0:
        msg = f"SGP4 error {err} at {t.isoformat()}"
        raise ValueError(msg)
    return np.array(r_km, dtype=np.float64)


def screen_pair_sphere_sgp4(
    my_line1: str,
    my_line2: str,
    external_line1: str,
    external_line2: str,
    start_utc: datetime,
    *,
    sphere_radius_km: float = 1.0,
    step_s: float = 30.0,
    search_max_orbits: int = 30,
    followup_orbits: int = 5,
    weight_distance: float = 0.5,
    weight_time: float = 0.5,
) -> PairSphereScreenResult:
    """Propagate both TLEs in lockstep; flag entry into a sphere around the ego sat.

    - **Ego** (``my_*``) defines a sphere of radius ``sphere_radius_km``.
    - At each sample, if range to the external object is < ``sphere_radius_km``,
      the external is inside the keep-out.
    - The time grid extends at least ``search_max_orbits`` of the ego period. If a first
      entry is found, the grid is extended to ``first_entry + followup_orbits * T_ego`` so
      at least five more ego orbits of data are taken after the first crossing (if the
      initial window was too short, the end is extended).

    **Heuristic probability** (not a CDM Pc): blend of (1) how deep the minimum pass is
    within the sphere scale and (2) fraction of the follow-up reference window (5 orbits)
    spent inside the sphere. Weights default to 0.5 / 0.5 and renormalize if only one
    non-zero.
    """
    if sphere_radius_km <= 0 or step_s <= 0:
        msg = "sphere_radius_km and step_s must be positive."
        raise ValueError(msg)

    t0 = start_utc.astimezone(UTC)
    T = _period_s_from_tle(my_line1, my_line2)
    follow_s = float(followup_orbits) * T

    ego = Satrec.twoline2rv(my_line1, my_line2, WGS72)
    ext = Satrec.twoline2rv(external_line1, external_line2, WGS72)

    # Dynamic end: at least search_max_orbits; may grow when first entry is found.
    end_t = t0 + timedelta(seconds=search_max_orbits * T)
    t_first: datetime | None = None

    min_d = float("inf")
    n_in = 0
    n_total = 0
    t = t0
    while t < end_t - 1e-9:
        p_ego = _position_km(ego, t)
        p_ext = _position_km(ext, t)
        d = float(np.linalg.norm(p_ext - p_ego))
        min_d = min(min_d, d)
        n_total += 1
        if d <= sphere_radius_km:
            n_in += 1
            if t_first is None:
                t_first = t
                need_end = t_first + timedelta(seconds=follow_s)
                if need_end > end_t:
                    end_t = need_end
        t += timedelta(seconds=step_s)

    time_inside_s = n_in * step_s
    conjunction = n_in > 0

    # Heuristic P: distance component (0 at r >= R, 1 at r=0), time component
    rel_ref = follow_s if follow_s > 0 else T
    score_d = max(0.0, 1.0 - min_d / sphere_radius_km) if sphere_radius_km > 0 else 0.0
    score_d = min(1.0, score_d)
    score_t = min(1.0, time_inside_s / rel_ref) if rel_ref > 0 else 0.0
    wd, wt = float(weight_distance), float(weight_time)
    s = wd + wt
    if s <= 0:
        wd, wt, s = 0.5, 0.5, 1.0
    else:
        wd, wt = wd / s, wt / s
    p_h = wd * score_d + wt * score_t
    p_h = max(0.0, min(1.0, p_h))

    return PairSphereScreenResult(
        conjunction_occurred=conjunction,
        closest_approach_km=min_d,
        first_entry_utc=t_first,
        my_orbital_period_s=T,
        time_points_inside_sphere=n_in,
        total_time_points=n_total,
        time_spent_inside_s=time_inside_s,
        integration_start_utc=t0,
        integration_end_utc=end_t,
        step_s=step_s,
        sphere_radius_km=sphere_radius_km,
        probability_heuristic=p_h,
        weight_distance=wd,
        weight_time=wt,
    )
