"""Lambert two-burn circular altitude transfer."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np

from node_api.lib.mission.circular_altitude_transfer import plan_lambert_two_burn_circular_altitude_change
from node_api.types.time import Epoch, TimeScale


def test_two_burn_raise_circular_leo() -> None:
    mu = 3.986004415e14
    r1_mag = 7_000_000.0
    r1 = np.array([r1_mag, 0.0, 0.0], dtype=np.float64)
    v_circ = math.sqrt(mu / r1_mag)
    v1 = np.array([0.0, v_circ, 0.0], dtype=np.float64)
    dep = Epoch(instant=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc), scale=TimeScale.UTC)
    plan = plan_lambert_two_burn_circular_altitude_change(
        r1,
        v1,
        target_circular_altitude_km=800.0,
        departure_epoch=dep,
        sat_id="TEST-1",
    )
    assert len(plan.maneuvers) == 2
    assert plan.objective == "lambert_two_burn_circular_altitude_change"
    assert plan.total_delta_v_mps > 0.0
    assert plan.time_of_flight_s is not None and plan.time_of_flight_s > 0.0
