"""Space-Track parsing (mocked) and SGP4 propagation via Skyfield."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from node_api.errors import DataUnavailableError
from node_api.lib.ingress import space_track as space_track_mod
from node_api.lib.ingress.space_track import SpaceTrackClient, fetch_tle, gp_record_to_tle
from node_api.lib.propagation import propagate_sgp4
from node_api.types.catalog import TLE
from node_api.types.common import Interval
from node_api.types.time import Epoch, TimeScale

_ISS_LINE1 = "1 25544U 98067A   24180.25000000  .00016717  00000+0  10270-3 0  9990"
_ISS_LINE2 = "2 25544  51.6416 355.6478 0007418  43.0265 317.0558 15.49408543 45756"
_ISS_GP = {
    "NORAD_CAT_ID": "25544",
    "EPOCH": "2024-06-28 06:00:00.0000",
    "MEAN_MOTION": "15.49408543",
    "ECCENTRICITY": "0007418",
    "INCLINATION": "51.6416",
    "RA_OF_ASC_NODE": "355.6478",
    "ARG_OF_PERICENTER": "43.0265",
    "MEAN_ANOMALY": "317.0558",
    "TLE_LINE1": _ISS_LINE1,
    "TLE_LINE2": _ISS_LINE2,
}


def test_gp_record_to_tle_round_trip_epoch() -> None:
    row = dict(_ISS_GP)
    tle = gp_record_to_tle(row)
    assert tle.satellite_number == 25544
    assert tle.line1 == _ISS_LINE1
    assert tle.epoch.scale == TimeScale.UTC


def test_propagate_sgp4_samples_ordered_and_frame() -> None:
    tle = TLE(
        line1=_ISS_LINE1,
        line2=_ISS_LINE2,
        epoch=Epoch(instant=datetime(2024, 6, 28, 6, 0, 0, tzinfo=UTC), scale=TimeScale.UTC),
        satellite_number=25544,
    )
    start = Epoch(instant=datetime(2024, 6, 15, 0, 0, 0, tzinfo=UTC), scale=TimeScale.UTC)
    end = Epoch(instant=datetime(2024, 6, 15, 2, 0, 0, tzinfo=UTC), scale=TimeScale.UTC)
    traj = propagate_sgp4(tle, Interval(start=start, end=end))
    assert traj.sat_id == "25544"
    assert len(traj.samples) >= 2
    assert len(traj.samples) <= 500
    times = [s.epoch.as_utc_datetime() for s in traj.samples]
    assert times == sorted(times)
    assert all(s.state.frame.value == "ECI_J2000" for s in traj.samples)


def test_fetch_tle_missing_credentials() -> None:
    with patch("node_api.lib.ingress.space_track.settings") as mock_settings:
        mock_settings.spacetrack_identity = None
        mock_settings.spacetrack_password = None
        mock_settings.spacetrack_user_agent = "test-agent"
        with pytest.raises(DataUnavailableError, match="credentials"):
            fetch_tle([25544])


def test_space_track_client_fetch_gp_tles() -> None:
    gp_json = [dict(_ISS_GP)]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/ajaxauth/login":
            return httpx.Response(200)
        if path.startswith("/basicspacedata/query/class/gp/"):
            return httpx.Response(200, json=gp_json)
        if path == "/ajaxauth/logout":
            return httpx.Response(200)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    real_client_cls = space_track_mod.httpx.Client

    def fake_client(**kwargs: Any) -> httpx.Client:
        return real_client_cls(
            transport=transport,
            base_url=kwargs["base_url"],
            headers=kwargs.get("headers"),
            timeout=kwargs["timeout"],
        )

    with patch.object(space_track_mod.httpx, "Client", side_effect=fake_client):
        with SpaceTrackClient("user", "pass", user_agent="unit-test") as client:
            out = client.fetch_gp_tles([25544])
            assert len(out) == 1
            assert out[0].satellite_number == 25544
