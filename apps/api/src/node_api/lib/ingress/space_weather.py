"""NOAA SWPC / space weather ingress (stubs)."""

from __future__ import annotations

from node_api.types.catalog import SpaceWeatherState
from node_api.types.time import Epoch


def fetch_latest_space_weather(at: Epoch | None = None) -> SpaceWeatherState:
    """Return the best available space weather snapshot near ``at``.

    Purpose:
        Drive density proxies (F10.7) and charging risk heuristics (Kp/Ap).

    When to use:
        Before long-horizon drag propagation or radiation environment checks.

    Prerequisites:
        Optional ``at``; defaults to "latest" per provider semantics.

    Post-checks:
        - Attach epoch to any derived ``Trajectory`` uncertainty scaling.

    Returns:
        ``SpaceWeatherState`` with scalar indices.

    Raises:
        DataUnavailableError: If indices are missing or stale beyond policy.
    """
    raise NotImplementedError
