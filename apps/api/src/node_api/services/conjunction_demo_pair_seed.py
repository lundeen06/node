"""Upsert a synthetic two-satellite pair for catalog-screen demos (SQLite).

Both use the same epoch and near-identical mean motion; **inclination (and RAAN for B)**
differ so the planes are not co-aligned, while SGP4 screening still finds a ~10 km
keep-out pass near TCA. Rows are tagged in ``gp_snapshot_json`` so
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

# Validated pair: screen_pair_sphere_sgp4 ~10.1 km miss, 12 km sphere, sim 2026-05-02 12:00 UTC.
_TLE_A1 = "1 98760U 26001A   26122.50000000  .00000000  00000-0  00000-0 0  9997"
_TLE_A2 = "2 98760  28.0000   0.0000 0001000   0.0000 350.0000 15.22004329    09"
_TLE_B1 = "1 98761U 26001B   26122.50000000  .00000000  00000-0  00000-0 0  9998"
_TLE_B2 = "2 98761  85.0000  40.0000 0001000   0.0000 330.0000 15.22104329    06"

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
    a_a = _semi_major_m_from_mean_motion_rev_day(15.22004329)
    a_b = _semi_major_m_from_mean_motion_rev_day(15.22104329)
    oe_a = [a_a, 1e-4, math.radians(28.0), 0.0, 0.0, math.radians(350.0)]
    oe_b = [a_b, 1e-4, math.radians(85.0), math.radians(40.0), 0.0, math.radians(330.0)]
    row_a = SpacecraftRow(
        sat_id=_SAT_A,
        name="Demo conjunction A (low incl.)",
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
        name="Demo conjunction B (high incl.)",
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


def ensure_demo_cross_plane_conjunction_pair(session: Session) -> None:
    """Merge the demo pair so catalog-screen can find a cross-plane close approach."""
    for row in _rows():
        session.merge(row)
    session.commit()
