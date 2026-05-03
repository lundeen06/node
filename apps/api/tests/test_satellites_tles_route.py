"""HTTP surface for Space-Track-backed TLE listing."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from node_api.main import app
from node_api.types.catalog import TLE
from node_api.types.time import Epoch, TimeScale

_ISS_LINE1 = "1 25544U 98067A   24180.25000000  .00016717  00000+0  10270-3 0  9990"
_ISS_LINE2 = "2 25544  51.6416 355.6478 0007418  43.0265 317.0558 15.49408543 45756"
_ISS_EPOCH = Epoch(instant=datetime(2024, 6, 28, 6, 0, 0, tzinfo=UTC), scale=TimeScale.UTC)


def test_get_satellites_tles_returns_gp_and_tle() -> None:
    row: dict[str, str | int] = {
        "NORAD_CAT_ID": "25544",
        "OBJECT_NAME": "ISS (NA)",
        "EPOCH": "2024-06-28 06:00:00.0000",
        "TLE_LINE1": _ISS_LINE1,
        "TLE_LINE2": _ISS_LINE2,
    }
    with patch("node_api.routes.satellites.fetch_gp_rows", return_value=[row]):
        client = TestClient(app)
        resp = client.get("/satellites/tles", params={"norad_ids": "25544"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["norad_catalog_id"] == 25544
    assert item["tle"]["line1"] == _ISS_LINE1
    assert item["gp"]["OBJECT_NAME"] == "ISS (NA)"


def test_get_satellites_tles_multiple_ids_order() -> None:
    rows = [
        {
            "NORAD_CAT_ID": "11111",
            "EPOCH": "2024-06-28 06:00:00.0000",
            "TLE_LINE1": _ISS_LINE1,
            "TLE_LINE2": _ISS_LINE2,
        },
        {
            "NORAD_CAT_ID": "22222",
            "EPOCH": "2024-06-28 06:00:00.0000",
            "TLE_LINE1": _ISS_LINE1,
            "TLE_LINE2": _ISS_LINE2,
        },
    ]

    def fake_fetch(ids: list[int]) -> list[dict[str, str]]:
        by_n = {int(r["NORAD_CAT_ID"]): r for r in rows}
        return [by_n[i] for i in ids]

    def fake_gp(row: dict[str, str]) -> TLE:
        return TLE(
            line1=row["TLE_LINE1"],
            line2=row["TLE_LINE2"],
            epoch=_ISS_EPOCH,
            satellite_number=int(str(row["NORAD_CAT_ID"])),
        )

    with (
        patch("node_api.routes.satellites.fetch_gp_rows", side_effect=fake_fetch),
        patch("node_api.routes.satellites.gp_record_to_tle", side_effect=fake_gp),
    ):
        client = TestClient(app)
        resp = client.get("/satellites/tles", params={"norad_ids": "22222,11111"})
    assert resp.status_code == 200
    out = resp.json()["items"]
    assert [x["norad_catalog_id"] for x in out] == [22222, 11111]
