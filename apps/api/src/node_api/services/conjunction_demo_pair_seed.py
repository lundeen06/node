"""Upsert two synthetic satellites for catalog-screen demos (SQLite).

Demo pair: same circular orbit shape, RAAN, arg-perigee, and mean anomaly; only the
**inclination** differs (45° vs 50°). Because both objects share epoch, mean motion, and
phase, they reach the ascending node simultaneously where their orbital planes intersect —
producing a near-zero-miss conjunction at the equator each orbit.

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

# Demo pair: same circular orbit shape/state, different inclinations (45 deg vs 50 deg).
_TLE_A1 = "1 98760U 26001A   26122.50000000  .00000000  00000-0  00000-0 0  9997"
_TLE_A2 = "2 98760  45.0000   0.0000 0000000   0.0000 350.0000 15.22004329    09"
_TLE_B1 = "1 98761U 26001B   26122.50000000  .00000000  00000-0  00000-0 0  9998"
_TLE_B2 = "2 98761  50.0000   0.0000 0000000   0.0000 350.0000 15.22004329    06"

_EPOCH = datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC)
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


def _rows() -> tuple[SpacecraftRow, SpacecraftRow]:
    now = datetime.now(tz=UTC)
    a_shared = _semi_major_m_from_mean_motion_rev_day(15.22004329)
    oe_a = [a_shared, 0.0, math.radians(45.0), 0.0, 0.0, math.radians(350.0)]
    oe_b = [a_shared, 0.0, math.radians(50.0), 0.0, 0.0, math.radians(350.0)]
    row_a = SpacecraftRow(
        sat_id=_SAT_A,
        name="Demo conjunction A (i=45°)",
        norad_catalog_id=_NORAD_A,
        purpose="Synthetic demo — not from Space-Track",
        gp_snapshot_json=json.dumps(_gp_stub(name="Demo conjunction A", norad=_NORAD_A)),
        tle_line1=_TLE_A1,
        tle_line2=_TLE_A2,
        oe_vector_json=json.dumps(oe_a),
        ephemeris_epoch_utc=_EPOCH,
        updated_at=now,
    )
    row_b = SpacecraftRow(
        sat_id=_SAT_B,
        name="Demo conjunction B (i=50°)",
        norad_catalog_id=_NORAD_B,
        purpose="Synthetic demo — not from Space-Track",
        gp_snapshot_json=json.dumps(_gp_stub(name="Demo conjunction B", norad=_NORAD_B)),
        tle_line1=_TLE_B1,
        tle_line2=_TLE_B2,
        oe_vector_json=json.dumps(oe_b),
        ephemeris_epoch_utc=_EPOCH,
        updated_at=now,
    )
    return row_a, row_b


_LEGACY_DEMO_SAT_IDS_TO_REMOVE: tuple[str, ...] = ("00-DEMO-STARLINK-CLONE-A",)


def ensure_demo_cross_plane_conjunction_pair(session: Session) -> None:
    """Merge the demo pair so catalog-screen finds the equatorial-node conjunction.

    Also cleans up any legacy demo rows that earlier seeders inserted into existing
    SQLite databases, so the demo set stays in sync with this seeder.
    """
    for legacy_sat_id in _LEGACY_DEMO_SAT_IDS_TO_REMOVE:
        legacy = session.get(SpacecraftRow, legacy_sat_id)
        if legacy is not None:
            session.delete(legacy)
    for row in _rows():
        session.merge(row)
    session.commit()
