"""POST /conjunctions/catalog-screen."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from node_api.db.models import ConjunctionEventRow
from node_api.db.session import SessionLocal
from node_api.main import app


def test_catalog_screen_returns_shape() -> None:
    client = TestClient(app)
    body = {"sim_utc": datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC).isoformat()}
    r = client.post("/conjunctions/catalog-screen", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "sim_utc" in data and "events" in data
    assert isinstance(data["events"], list)

    db = SessionLocal()
    try:
        n = int(db.scalar(select(func.count()).select_from(ConjunctionEventRow)) or 0)
    finally:
        db.close()
    assert n == len(data["events"]), "catalog-screen should persist the same event count to SQLite"


def test_catalog_screen_maneuver_preview_requires_sat_id() -> None:
    client = TestClient(app)
    body = {
        "sim_utc": datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC).isoformat(),
        "maneuver_preview_maneuvers": [
            {
                "epoch_utc": datetime(2026, 5, 2, 13, 0, 0, tzinfo=UTC).isoformat(),
                "delta_v_mps": {"x": 0.0, "y": 0.0, "z": 1.0},
                "frame": "ECI",
            },
        ],
    }
    r = client.post("/conjunctions/catalog-screen", json=body)
    assert r.status_code == 422, r.text


def test_catalog_screen_accepts_maneuver_preview_payload() -> None:
    client = TestClient(app)
    body = {
        "sim_utc": datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC).isoformat(),
        "maneuver_preview_sat_id": "DEMO-SAT-1",
        "maneuver_preview_maneuvers": [
            {
                "epoch_utc": datetime(2026, 5, 2, 13, 0, 0, tzinfo=UTC).isoformat(),
                "delta_v_mps": {"x": 0.0, "y": 0.0, "z": 0.5},
                "frame": "ECI",
            },
        ],
    }
    r = client.post("/conjunctions/catalog-screen", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "events" in data
