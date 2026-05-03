"""Synthetic ISS (NORAD 25544) row for local demos — no Space-Track call (skipped by sync)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from node_api.db.models import SpacecraftRow
from node_api.services.spacecraft_catalog import upsert_spacecraft_from_gp

ISS_DEMO_SAT_ID = "ISS-25544"
ISS_DEMO_NORAD = 25544

_ISS_LINE1 = "1 25544U 98067A   24180.25000000  .00016717  00000+0  10270-3 0  9990"
_ISS_LINE2 = "2 25544  51.6416 355.6478 0007418  43.0265 317.0558 15.49408543 45756"


def _iss_gp() -> dict[str, Any]:
    """Fields required by ``gp_record_to_absolute_elements`` / ``upsert_spacecraft_from_gp``."""
    return {
        "OBJECT_NAME": "ISS (demo)",
        "NORAD_CAT_ID": str(ISS_DEMO_NORAD),
        "EPOCH": "2024-06-28 06:00:00.0000",
        "MEAN_MOTION": 15.49408543,
        "ECCENTRICITY": "0007418",
        "INCLINATION": 51.6416,
        "RA_OF_ASC_NODE": 355.6478,
        "ARG_OF_PERICENTER": 43.0265,
        "MEAN_ANOMALY": 317.0558,
        "synthetic_demo_tle": True,
        "TLE_LINE1": _ISS_LINE1,
        "TLE_LINE2": _ISS_LINE2,
    }


def ensure_demo_iss_catalog_row(session: Session) -> None:
    """Upsert a stable ISS demo TLE so agents and UI can use ``ISS-25544`` or NORAD ``25544``."""
    session.execute(delete(SpacecraftRow).where(SpacecraftRow.norad_catalog_id == ISS_DEMO_NORAD))
    session.commit()
    gp = _iss_gp()
    upsert_spacecraft_from_gp(
        session,
        sat_id=ISS_DEMO_SAT_ID,
        name="ISS (demo)",
        norad_catalog_id=ISS_DEMO_NORAD,
        purpose="Synthetic ISS TLE for local demo — not live Space-Track",
        gp=gp,
    )
