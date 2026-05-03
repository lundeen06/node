"""TLE → classical elements via SGP4 at an epoch, then physics-layer propagation."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
from sgp4.api import WGS72, Satrec
from sgp4.conveniences import jday_datetime

from node_api.errors import DataUnavailableError
from node_api.physics_runtime import ensure_physics_importable

ensure_physics_importable()
from physics.infra.slate import AbsoluteOrbitalElements  # noqa: E402
from physics.propulsion import util_dyn  # noqa: E402


def tle_to_absolute_elements_at_epoch(line1: str, line2: str, epoch_utc: datetime) -> AbsoluteOrbitalElements:
    """Evaluate SGP4 at ``epoch_utc`` and convert Cartesian PV to classical elements (``util_dyn`` convention)."""
    sat = Satrec.twoline2rv(line1, line2, WGS72)
    jd, fr = jday_datetime(epoch_utc.astimezone(UTC))
    err, r_km, v_km_s = sat.sgp4(jd, fr)
    if err != 0:
        msg = f"SGP4 propagation failed at epoch (error code {err})."
        raise DataUnavailableError(msg)
    pv = np.concatenate([np.asarray(r_km, dtype=np.float64) * 1000.0, np.asarray(v_km_s, dtype=np.float64) * 1000.0])
    oe = util_dyn.pv_to_oe(pv, util_dyn.mu_E)
    return AbsoluteOrbitalElements.from_vector(tuple(float(x) for x in oe))
