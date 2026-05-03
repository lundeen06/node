"""Approximate ECI (oe_to_pv frame) to geographic coordinates for map clients."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import numpy as np
from numpy.typing import NDArray


def _julian_date(dt: datetime) -> float:
    """Julian date for UTC instant (calendar algorithm)."""
    dt = dt.astimezone(UTC)
    y, m = dt.year, dt.month
    d = (
        dt.day
        + dt.hour / 24.0
        + dt.minute / 1440.0
        + dt.second / 86400.0
        + dt.microsecond / 86400e6
    )
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd = math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5
    return float(jd)


def gmst_radians(dt_utc: datetime) -> float:
    """Greenwich Mean Sidereal Time (approximation; UTC used as UT1 substitute)."""
    jd = _julian_date(dt_utc)
    t = (jd - 2451545.0) / 36525.0
    gmst_deg = (
        280.46061837
        + 360.98564736629 * (jd - 2451545.0)
        + 0.000387933 * t * t
        - t * t * t / 38710000.0
    )
    return math.radians(gmst_deg % 360.0)


def eci_m_to_lon_lat_deg(r_eci_m: NDArray[np.float64], dt_utc: datetime) -> tuple[float, float]:
    """Rotate approximate ECI → ECEF via z-axis GMST; return (lon, lat) degrees."""
    gmst = gmst_radians(dt_utc)
    c, s = math.cos(gmst), math.sin(gmst)
    r = np.asarray(r_eci_m, dtype=np.float64).reshape(3)
    x = c * r[0] + s * r[1]
    y = -s * r[0] + c * r[1]
    z = r[2]
    lon_rad = math.atan2(y, x)
    lat_rad = math.atan2(z, math.hypot(x, y))
    return math.degrees(lon_rad), math.degrees(lat_rad)
