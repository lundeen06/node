"""Planner library routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from node_api.main import create_app


def test_planner_lambert_chord_ok() -> None:
    app = create_app()
    client = TestClient(app)
    body = {
        "r0_m": [5_000_000.0, 10_000_000.0, 2_100_000.0],
        "r_m": [-14_600_000.0, 2_500_000.0, 7_000_000.0],
        "tof_s": 3600.0,
        "mu_m3_s2": 398_600.4418e9,
        "prograde": True,
    }
    res = client.post("/planner/lambert/chord", json=body)
    assert res.status_code == 200
    data = res.json()
    assert "v0_mps" in data and "v1_mps" in data
    assert len(data["v0_mps"]) == 3


def test_planner_lambert_chord_validation_negative_tof() -> None:
    app = create_app()
    client = TestClient(app)
    res = client.post(
        "/planner/lambert/chord",
        json={
            "r0_m": [7_000_000.0, 0.0, 0.0],
            "r_m": [7_100_000.0, 0.0, 0.0],
            "tof_s": -10.0,
            "prograde": True,
        },
    )
    assert res.status_code == 422
