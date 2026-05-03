"""Pair conjunction screening using matched classical elements + mean-element propagation.

Scenario: ego satellite equatorial circular ``a = 7000 km``; secondary differs only in
semi-major axis. Same ``Ω, ω, i, e``, same mean anomaly at ``t₀``. Propagate both for
**five ego orbital periods** (two-body, ``J2 = 0``). Flag conjunction when range drops
below **1 km** (keep-out sphere).

With nearly equal semi-major axes, mean-motion drift is tiny over five orbits, so the
pair stays almost **in phase**; range stays near ``|a_ext − a_ego|`` (km). For
``a_ext = 7000.01`` km that separation is 10 m ⇒ always inside a 1 km sphere; for
``7002`` km it is 2 km ⇒ never inside.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from node_api.physics_runtime import ensure_physics_importable

ensure_physics_importable()
from physics.propulsion import util_dyn  # noqa: E402


def _ego_period_s(a_m: float, mu: float) -> float:
    return 2.0 * math.pi * math.sqrt(a_m**3 / mu)


def _scan_pair_min_distance_km(
    a_ego_km: float,
    a_ext_km: float,
    *,
    ecc: float,
    num_orbits: float,
    step_s: float,
    sphere_km: float,
) -> tuple[bool, float, int, int, float]:
    """Return (conjunction_occurred, min_distance_km, samples_inside, total_samples, duration_s)."""
    mu = util_dyn.mu_E
    a0_m = a_ego_km * 1000.0
    a1_m = a_ext_km * 1000.0

    T = _ego_period_s(a0_m, mu)
    duration_s = num_orbits * T

    # Equatorial; identical Ω, ω, M₀
    oe_ego = np.array([a0_m, ecc, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)
    oe_ext = np.array([a1_m, ecc, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)

    min_d = float("inf")
    n_in = 0
    n_tot = 0
    t = 0.0
    while t < duration_s + 1e-9:
        g_e = util_dyn.propagate_oe(oe_ego, t, mu=mu, J2=0.0)
        g_x = util_dyn.propagate_oe(oe_ext, t, mu=mu, J2=0.0)
        pv_e = util_dyn.oe_to_pv(g_e, mu)
        pv_x = util_dyn.oe_to_pv(g_x, mu)
        r_e = pv_e[0:3] / 1000.0
        r_x = pv_x[0:3] / 1000.0
        d_km = float(np.linalg.norm(r_x - r_e))
        min_d = min(min_d, d_km)
        n_tot += 1
        if d_km <= sphere_km:
            n_in += 1
        t += step_s

    return (n_in > 0), min_d, n_in, n_tot, duration_s


@pytest.mark.parametrize(
    ("a_ext_km", "expect_conjunction"),
    [
        (7002.0, False),
        (7000.01, True),
    ],
)
def test_equatorial_pair_five_orbits_keep_out_1km(
    a_ext_km: float,
    expect_conjunction: bool,
) -> None:
    """7000 km ego vs 7002 km → stay outside 1 km; vs 7000.01 km → inside sphere."""
    ecc = 1e-8
    a_ego_km = 7000.0
    conj, min_d, n_in, n_tot, dur = _scan_pair_min_distance_km(
        a_ego_km,
        a_ext_km,
        ecc=ecc,
        num_orbits=5.0,
        step_s=30.0,
        sphere_km=1.0,
    )

    # Visible with: pytest tests/test_conjunction_keplerian_pairs.py -v -s
    print()
    print("=== Keplerian pair conjunction scan (mean elements, J2=0) ===")
    print(f"  ego a = {a_ego_km} km  |  other a = {a_ext_km} km  |  e = {ecc}")
    print(f"  keep-out radius = 1.0 km")
    print(f"  window = 5 × ego period ≈ {dur:.1f} s")
    print(f"  samples: {n_tot}, step = 30 s")
    print(f"  minimum range = {min_d:.6f} km")
    print(f"  samples inside sphere = {n_in}")
    print(f"  conjunction_occurred = {conj}")
    print(f"  expected conjunction = {expect_conjunction}")

    assert conj is expect_conjunction
    if expect_conjunction:
        assert min_d <= 1.0
    else:
        assert min_d > 1.0
