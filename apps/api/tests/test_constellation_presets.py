"""Constellation preset GP merging and validation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from node_api.lib.ingress.constellation_presets import fetch_gp_constellation, require_preset


def _minimal_gp(norad: int, name: str) -> dict[str, str]:
    return {
        "NORAD_CAT_ID": str(norad),
        "OBJECT_NAME": name,
        "EPOCH": "2024-06-28 06:00:00.0000",
        "MEAN_MOTION": "15.49408543",
        "ECCENTRICITY": "0.0007418",
        "INCLINATION": "51.6416",
        "RA_OF_ASC_NODE": "355.6478",
        "ARG_OF_PERICENTER": "43.0265",
        "MEAN_ANOMALY": "317.0558",
        "TLE_LINE1": "1 25544U 98067A   24180.25000000  .00016717  00000+0  10270-3 0  9990",
        "TLE_LINE2": "2 25544  51.6416 355.6478 0007418  43.0265 317.0558 15.49408543 45756",
    }


def test_require_preset_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        require_preset("not-a-real-preset")


def test_fetch_gp_constellation_merges_by_norad_and_truncates() -> None:
    """Two patterns return duplicate NORAD — keep first; ``limit`` truncates."""
    rows_a = [_minimal_gp(10, "KUIPER-10")]
    rows_b = [_minimal_gp(10, "KUIPER-10-DUP"), _minimal_gp(11, "KUIPER-11")]
    with patch("node_api.lib.ingress.constellation_presets.query_gp", side_effect=[rows_a, rows_b]):
        out, truncated = fetch_gp_constellation("kuiper", limit=1, timeout_s=60.0)
    assert truncated is True
    assert len(out) == 1
    assert str(out[0]["NORAD_CAT_ID"]) == "10"


def test_fetch_gp_constellation_planet_runs_multiple_queries() -> None:
    with patch(
        "node_api.lib.ingress.constellation_presets.query_gp",
        side_effect=[
            [_minimal_gp(1, "SKYSAT-1")],
            [_minimal_gp(2, "FLOCK-2")],
            [_minimal_gp(3, "DOVE-3")],
            [_minimal_gp(4, "PLANET-4")],
        ],
    ) as q:
        out, truncated = fetch_gp_constellation("planet", limit=None, timeout_s=60.0)
    assert q.call_count == 4
    assert len(out) == 4
    assert truncated is False
