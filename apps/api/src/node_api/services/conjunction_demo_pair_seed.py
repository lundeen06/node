"""Upsert two synthetic satellites for catalog-screen demos (SQLite).

Demo pair: same circular orbit shape, RAAN, arg-perigee, and mean anomaly; only the
**inclination** differs (45° vs 50°). Because both objects share epoch, mean motion, and
phase, they reach the ascending node simultaneously where their orbital planes intersect —
producing a near-zero-miss conjunction at the equator each orbit.

The TLE epoch is **rebuilt at seed time to "now"** so SGP4 J2 RAAN drift hasn't yet
separated the two orbital planes (the differential is ``cos(45°) − cos(50°) ≈ 0.064`` per
day). Otherwise stale-epoch TLEs would no longer share a common AN line and screening
would miss the conjunction entirely.

Rows are tagged in ``gp_snapshot_json`` (``synthetic_demo_tle: true``) so
``sync_all_registered`` skips them (no Space-Track GP for test NORADs).
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from node_api.db.models import SpacecraftRow

_SAT_A = "00-DEMO-CNJ-A"
_SAT_B = "00-DEMO-CNJ-B"
_NORAD_A = 98760
_NORAD_B = 98761

# Static TLE templates: same circular orbit shape/state, different inclinations (45 vs 50 deg).
# The epoch field (cols 19-32 of line 1) and the line checksums are rewritten in ``_rows()``
# so the demo always uses a fresh epoch — see module docstring.
_TLE_A1_TEMPLATE = "1 98760U 26001A   00000.00000000  .00000000  00000-0  00000-0 0  9990"
_TLE_A2 = "2 98760  45.0000   0.0000 0000000   0.0000 350.0000 15.22004329    09"
_TLE_B1_TEMPLATE = "1 98761U 26001B   00000.00000000  .00000000  00000-0  00000-0 0  9990"
_TLE_B2 = "2 98761  50.0000   0.0000 0000000   0.0000 350.0000 15.22004329    06"

_MU_M3S2 = 398600441800000.0


def _semi_major_m_from_mean_motion_rev_day(mm: float) -> float:
    n_rad_s = mm * (2.0 * math.pi) / 86400.0
    return float((_MU_M3S2 / (n_rad_s**2)) ** (1.0 / 3.0))


def _gp_stub(*, name: str, norad: int) -> dict[str, Any]:
    return {
        "OBJECT_NAME": name,
        "NORAD_CAT_ID": norad,
        "synthetic_demo_tle": True,
    }


def _tle_checksum(line_without_checksum: str) -> str:
    """Standard TLE checksum: (sum of digit values + count of '-' chars) mod 10."""
    s = 0
    for ch in line_without_checksum:
        if ch.isdigit():
            s += int(ch)
        elif ch == "-":
            s += 1
    return str(s % 10)


def _format_tle_epoch_field(dt: datetime) -> str:
    """``YYDDD.DDDDDDDD`` (14 chars) for TLE line 1 cols 19-32."""
    dt_utc = dt.astimezone(UTC)
    yy = dt_utc.year % 100
    year_start = datetime(dt_utc.year, 1, 1, tzinfo=UTC)
    day_of_year = (dt_utc - year_start).total_seconds() / 86400.0 + 1.0
    return f"{yy:02d}{day_of_year:012.8f}"


def _set_tle_line1_epoch(template_line1: str, dt: datetime) -> str:
    """Replace the epoch field (cols 19-32) and recompute the checksum."""
    epoch_field = _format_tle_epoch_field(dt)
    if len(epoch_field) != 14:
        msg = f"TLE epoch field length {len(epoch_field)}, expected 14"
        raise ValueError(msg)
    body = template_line1[:18] + epoch_field + template_line1[32:68]
    if len(body) != 68:
        msg = f"TLE line 1 body length {len(body)}, expected 68"
        raise ValueError(msg)
    return body + _tle_checksum(body)


def _rows(tle_epoch: datetime | None = None) -> tuple[SpacecraftRow, SpacecraftRow]:
    now = datetime.now(tz=UTC)
    epoch = (tle_epoch or now).astimezone(UTC)
    tle_a1 = _set_tle_line1_epoch(_TLE_A1_TEMPLATE, epoch)
    tle_b1 = _set_tle_line1_epoch(_TLE_B1_TEMPLATE, epoch)
    a_shared = _semi_major_m_from_mean_motion_rev_day(15.22004329)
    oe_a = [a_shared, 0.0, math.radians(45.0), 0.0, 0.0, math.radians(350.0)]
    oe_b = [a_shared, 0.0, math.radians(50.0), 0.0, 0.0, math.radians(350.0)]
    row_a = SpacecraftRow(
        sat_id=_SAT_A,
        name="Demo conjunction A (i=45°)",
        norad_catalog_id=_NORAD_A,
        purpose="Synthetic demo — not from Space-Track",
        gp_snapshot_json=json.dumps(_gp_stub(name="Demo conjunction A", norad=_NORAD_A)),
        tle_line1=tle_a1,
        tle_line2=_TLE_A2,
        oe_vector_json=json.dumps(oe_a),
        ephemeris_epoch_utc=epoch,
        updated_at=now,
    )
    row_b = SpacecraftRow(
        sat_id=_SAT_B,
        name="Demo conjunction B (i=50°)",
        norad_catalog_id=_NORAD_B,
        purpose="Synthetic demo — not from Space-Track",
        gp_snapshot_json=json.dumps(_gp_stub(name="Demo conjunction B", norad=_NORAD_B)),
        tle_line1=tle_b1,
        tle_line2=_TLE_B2,
        oe_vector_json=json.dumps(oe_b),
        ephemeris_epoch_utc=epoch,
        updated_at=now,
    )
    return row_a, row_b


_LEGACY_DEMO_SAT_IDS_TO_REMOVE: tuple[str, ...] = ("00-DEMO-STARLINK-CLONE-A",)
DEMO_PAIR_SAT_IDS: tuple[str, ...] = (_SAT_A, _SAT_B)


def ensure_demo_cross_plane_conjunction_pair(
    session: Session,
    *,
    tle_epoch: datetime | None = None,
) -> None:
    """Merge the demo pair so catalog-screen finds the equatorial-node conjunction.

    ``tle_epoch`` (optional) lets callers re-stamp the TLE epoch to a specific sim instant
    so SGP4 J2 RAAN drift hasn't yet pulled the 45° and 50° planes apart by the time
    screening evaluates them. Defaults to wall-clock now when omitted.

    Also cleans up any legacy demo rows that earlier seeders inserted into existing
    SQLite databases, so the demo set stays in sync with this seeder.
    """
    for legacy_sat_id in _LEGACY_DEMO_SAT_IDS_TO_REMOVE:
        legacy = session.get(SpacecraftRow, legacy_sat_id)
        if legacy is not None:
            session.delete(legacy)
    for row in _rows(tle_epoch=tle_epoch):
        session.merge(row)
    session.commit()


# How far the demo's stored TLE epoch may drift from a requested ``sim_utc`` before we
# re-stamp it. Beyond this delta, J2 RAAN drift starts separating the 45/50 planes (we
# verified ~50 km miss after 6h, ~165 km after 24h — see commit message).
_DEMO_REFRESH_THRESHOLD_S: float = 30 * 60.0


def refresh_demo_pair_for_sim_utc(session: Session, sim_utc: datetime) -> bool:
    """Re-stamp the demo TLE epoch to ``sim_utc`` if the stored epoch has drifted too far.

    Returns ``True`` when the demo rows were rewritten. Designed to be called by the
    catalog-screen route so the demo conjunction is always visible regardless of how fast
    the operator's sim clock has advanced past startup.
    """
    target = sim_utc.astimezone(UTC)
    existing = session.get(SpacecraftRow, _SAT_A)
    if existing is not None and existing.ephemeris_epoch_utc is not None:
        current = existing.ephemeris_epoch_utc.astimezone(UTC)
        delta_s = abs((target - current).total_seconds())
        if delta_s <= _DEMO_REFRESH_THRESHOLD_S:
            return False
    ensure_demo_cross_plane_conjunction_pair(session, tle_epoch=target)
    return True
