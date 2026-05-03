"""TLE → classical elements via SGP4 at an epoch, then physics-layer propagation."""

from __future__ import annotations

import math
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


def sgp4_position_eci_m(line1: str, line2: str, when_utc: datetime) -> np.ndarray:
    """SGP4 position in km (TEME/ECI-like) converted to **meters** for geodesy helpers."""
    sat = Satrec.twoline2rv(line1, line2, WGS72)
    jd, fr = jday_datetime(when_utc.astimezone(UTC))
    err, r_km, _v_km_s = sat.sgp4(jd, fr)
    if err != 0:
        msg = f"SGP4 propagation failed (error code {err})."
        raise DataUnavailableError(msg)
    return np.asarray(r_km, dtype=np.float64) * 1000.0


def tle_orbital_period_kozai_s(line1: str, line2: str) -> float:
    """Sidereal period from SGP4 Kozai mean motion (rad/min), seconds."""
    sat = Satrec.twoline2rv(line1, line2, WGS72)
    nm = float(sat.no_kozai)
    if nm <= 0:
        msg = "TLE has invalid mean motion (no_kozai <= 0)."
        raise DataUnavailableError(msg)
    return 2.0 * math.pi * 60.0 / nm


def trajectory_states_sgp4(
    line1: str,
    line2: str,
    times_utc: list[datetime],
) -> list[tuple[datetime, np.ndarray, np.ndarray]]:
    """For each UTC time: ``(t, r_km (3,), v_km_s (3,))`` via NORAD SGP4."""
    sat = Satrec.twoline2rv(line1, line2, WGS72)
    out: list[tuple[datetime, np.ndarray, np.ndarray]] = []
    for t in times_utc:
        tt = t.astimezone(UTC)
        jd, fr = jday_datetime(tt)
        err, r_km, v_km_s = sat.sgp4(jd, fr)
        if err != 0:
            msg = f"SGP4 propagation failed at {tt.isoformat()} (error code {err})."
            raise DataUnavailableError(msg)
        rk = np.asarray(r_km, dtype=np.float64)
        vk = np.asarray(v_km_s, dtype=np.float64)
        out.append((tt, rk, vk))
    return out
