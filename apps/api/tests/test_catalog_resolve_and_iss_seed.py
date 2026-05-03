"""Catalog resolution (sat_id / NORAD / name) and ISS demo seed."""

from __future__ import annotations

from node_api.db.session import SessionLocal
from node_api.services.catalog_demo_iss_seed import ISS_DEMO_NORAD, ISS_DEMO_SAT_ID, ensure_demo_iss_catalog_row
from node_api.services.spacecraft_catalog import resolve_spacecraft_row


def test_resolve_iss_by_norad_name_and_sat_id() -> None:
    db = SessionLocal()
    try:
        ensure_demo_iss_catalog_row(db)
        a = resolve_spacecraft_row(db, str(ISS_DEMO_NORAD))
        assert a is not None
        assert a.sat_id == ISS_DEMO_SAT_ID
        assert a.norad_catalog_id == ISS_DEMO_NORAD
        b = resolve_spacecraft_row(db, "ISS (demo)")
        assert b is not None and b.sat_id == ISS_DEMO_SAT_ID
        c = resolve_spacecraft_row(db, ISS_DEMO_SAT_ID)
        assert c is not None and c.norad_catalog_id == ISS_DEMO_NORAD
        d = resolve_spacecraft_row(db, "NORAD 25544 for ISS")
        assert d is not None and d.sat_id == ISS_DEMO_SAT_ID
    finally:
        db.close()
