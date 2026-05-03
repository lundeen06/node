"""Pair screening from classical elements: keep-out sphere around ego, mean-element propagation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from node_api.lib.solvers.lambert import _keplerian_to_oe_vector_m
from node_api.physics_runtime import ensure_physics_importable
from node_api.types.state import KeplerianElements
from node_api.types.time import Epoch

ensure_physics_importable()
from physics.propulsion import util_dyn  # noqa: E402


@dataclass(frozen=True, slots=True)
class KeplerianPairKeepoutResult:
    conjunction_occurred: bool
    first_conjunction_utc: datetime | None
    conjunction_score_normalized: float
    closest_approach_km: float
    time_points_inside_sphere: int
    total_time_points: int
    integration_start_utc: datetime
    integration_end_utc: datetime
    step_s: float
    horizon_s: float
    keep_out_sphere_radius_km: float
    weight_distance_applied: float
    weight_time_applied: float


def screen_pair_keplerian_keepout(
    my_elements: KeplerianElements,
    external_elements: KeplerianElements,
    start_epoch: Epoch,
    horizon_duration_s: float,
    keep_out_sphere_radius_km: float,
    *,
    step_s: float = 30.0,
    weight_distance: float = 0.5,
    weight_time: float = 0.5,
    use_j2: bool = False,
) -> KeplerianPairKeepoutResult:
    """Forward-propagate both osculating mean-element sets; detect external inside ego sphere.

    At each sample ``t`` from ``start_epoch`` over ``horizon_duration_s``:

    - Range ``d`` (km) between Cartesian positions (``oe_to_pv`` after ``propagate_oe``).
    - **Proximity** term: ``max(0, 1 - d / R)`` with ``R = keep_out_sphere_radius_km``.
    - **Dwell** term: ``1`` if ``d <= R`` else ``0``.

    Per-timestep score: ``w_d * proximity + w_t * dwell`` (weights renormalized to sum 1).

    **Normalized conjunction score** (per your spec): ``(sum of per-timestep scores) / N``
    where ``N`` is the number of samples — i.e. the **mean** per-step hazard in ``[0, 1]``.

    ``first_conjunction_utc`` is the first sample time with ``d <= R`` (``None`` if never).
    """
    if horizon_duration_s <= 0 or keep_out_sphere_radius_km <= 0 or step_s <= 0:
        msg = "horizon_duration_s, keep_out_sphere_radius_km, and step_s must be positive."
        raise ValueError(msg)

    mu = util_dyn.mu_E
    j2 = util_dyn.J2 if use_j2 else 0.0

    oe_m = _keplerian_to_oe_vector_m(my_elements)
    oe_x = _keplerian_to_oe_vector_m(external_elements)

    t0 = start_epoch.as_utc_datetime().astimezone(timezone.utc)
    end = t0 + timedelta(seconds=float(horizon_duration_s))

    wd, wt = float(weight_distance), float(weight_time)
    s = wd + wt
    if s <= 0:
        wd, wt = 0.5, 0.5
    else:
        wd, wt = wd / s, wt / s

    r_sphere = float(keep_out_sphere_radius_km)
    min_d = float("inf")
    n_in = 0
    n_tot = 0
    score_sum = 0.0
    t_first = None
    t = 0.0
    while t < horizon_duration_s + 1e-9:
        g_m = util_dyn.propagate_oe(oe_m, t, mu=mu, J2=j2)
        g_x = util_dyn.propagate_oe(oe_x, t, mu=mu, J2=j2)
        pv_m = util_dyn.oe_to_pv(g_m, mu)
        pv_x = util_dyn.oe_to_pv(g_x, mu)
        r_m = pv_m[0:3] / 1000.0
        r_x = pv_x[0:3] / 1000.0
        d_km = float(np.linalg.norm(r_x - r_m))
        min_d = min(min_d, d_km)

        prox = max(0.0, 1.0 - d_km / r_sphere) if r_sphere > 0 else 0.0
        prox = min(1.0, prox)
        dwell = 1.0 if d_km <= r_sphere else 0.0
        score_sum += wd * prox + wt * dwell
        n_tot += 1

        if d_km <= r_sphere:
            n_in += 1
            if t_first is None:
                t_first = t0 + timedelta(seconds=float(t))

        t += step_s

    if not math.isfinite(min_d):
        min_d = float("nan")

    score_norm = score_sum / float(n_tot) if n_tot > 0 else 0.0

    return KeplerianPairKeepoutResult(
        conjunction_occurred=n_in > 0,
        first_conjunction_utc=t_first,
        conjunction_score_normalized=score_norm,
        closest_approach_km=min_d,
        time_points_inside_sphere=n_in,
        total_time_points=n_tot,
        integration_start_utc=t0,
        integration_end_utc=end,
        step_s=step_s,
        horizon_s=float(horizon_duration_s),
        keep_out_sphere_radius_km=r_sphere,
        weight_distance_applied=wd,
        weight_time_applied=wt,
    )
