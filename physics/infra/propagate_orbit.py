"""Propagate classical orbital elements using :func:`physics.propulsion.util_dyn.propagate_oe`."""

from __future__ import annotations

import numpy as np

from physics.infra.slate import AbsoluteOrbitalElements
from physics.propulsion import util_dyn


def propagate_absolute_elements(
    elements: AbsoluteOrbitalElements,
    times_s: np.ndarray,
    *,
    use_j2: bool = True,
) -> np.ndarray:
    """Propagate ``elements`` to each elapsed time in ``times_s`` (seconds from epoch).

    Returns:
        Array of shape (6, N): columns are Cartesian position (m) and velocity (m/s) in the
        same ECI frame as :func:`physics.propulsion.util_dyn.oe_to_pv`.
    """
    oe0 = np.asarray(elements.as_vector(), dtype=np.float64)
    dt = np.asarray(times_s, dtype=np.float64).reshape(-1)
    j2 = util_dyn.J2 if use_j2 else 0.0
    oe_series = util_dyn.propagate_oe(oe0, dt, mu=util_dyn.mu_E, R=util_dyn.R_E, J2=j2)
    if oe_series.ndim == 1:
        return np.asarray(util_dyn.oe_to_pv(oe_series), dtype=np.float64).reshape(6, 1)
    n = oe_series.shape[1]
    out = np.zeros((6, n), dtype=np.float64)
    for j in range(n):
        out[:, j] = util_dyn.oe_to_pv(oe_series[:, j])
    return out


__all__ = ["propagate_absolute_elements"]
