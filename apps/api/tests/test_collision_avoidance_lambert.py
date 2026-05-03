"""Lambert integration in collision avoidance solvers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

from node_api.lib.mission.collision_avoidance import plan_collision_avoidance
from node_api.lib.solvers.avoidance import solve_impulsive_avoidance
from node_api.types.common import Matrix6x6, Vector3
from node_api.types.conjunction import CloseApproach, Conjunction, ConjunctionSource, ConjunctionStatus, PcMethod
from node_api.types.constellation import HouseRules
from node_api.types.frames import Frame
from node_api.types.satellite import DataQuality, SatelliteState
from node_api.types.state import Covariance6x6, StateVector
from node_api.types.time import Epoch, TimeScale


def _epoch(dt: datetime) -> Epoch:
    return Epoch(instant=dt, scale=TimeScale.UTC)


def _ego(sat_id: str, t0: datetime) -> SatelliteState:
    s = StateVector(
        position_km=Vector3(data=np.array([7000.0, 0.0, 0.0], dtype=np.float64)),
        velocity_km_s=Vector3(data=np.array([0.0, 7.5, 0.0], dtype=np.float64)),
        epoch=_epoch(t0),
        frame=Frame.ECI_J2000,
    )
    cov = Covariance6x6(
        matrix=Matrix6x6(data=np.diag([1.0, 1.0, 1.0, 1e-6, 1e-6, 1e-6]).astype(np.float64)),
        epoch=s.epoch,
        frame=s.frame,
    )
    return SatelliteState(
        sat_id=sat_id,
        state_vector=s,
        covariance=cov,
        fuel_kg=50.0,
        last_updated=s.epoch,
        data_quality=DataQuality.NOMINAL,
    )


def _threat(tca: datetime) -> CloseApproach:
    return CloseApproach(
        id="CNJ-TEST",
        primary_id="EGO-1",
        secondary_id="DEB-1",
        tca=_epoch(tca),
        miss_distance_km=0.5,
        relative_velocity_km_s=14.0,
        source=ConjunctionSource.INTERNAL_SCREENING,
        created_at=_epoch(tca - timedelta(hours=1)),
    )


def test_solve_impulsive_avoidance_returns_lambert_plan() -> None:
    t0 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    tca = t0 + timedelta(hours=2)
    ego = _ego("EGO-1", t0)
    threat = _threat(tca)
    plan = solve_impulsive_avoidance(ego, threat, max_delta_v_mps=500.0, pc_target=1e-4)
    assert plan.sat_id == "EGO-1"
    assert len(plan.maneuvers) == 1
    assert plan.maneuvers[0].frame.value == "ECI"
    assert plan.total_delta_v_mps > 0
    assert "lambert_collision_avoidance" in plan.objective


def test_plan_collision_avoidance_from_conjunction() -> None:
    t0 = datetime(2026, 3, 2, 0, 0, 0, tzinfo=UTC)
    tca = t0 + timedelta(hours=3)
    ego = _ego("EGO-2", t0)
    conj = Conjunction(
        id="CNJ-X",
        primary_id="EGO-2",
        secondary_id="DEB-9",
        tca=_epoch(tca),
        miss_distance_km=0.2,
        relative_velocity_km_s=10.0,
        pc=1e-3,
        pc_method=PcMethod.MONTE_CARLO,
        source=ConjunctionSource.INTERNAL_SCREENING,
        created_at=_epoch(t0),
        status=ConjunctionStatus.NEW,
    )
    rules = HouseRules(
        constellation_id="DEMO",
        max_auto_delta_v_mps=800.0,
        pc_mitigation_threshold=1e-4,
    )
    plan = plan_collision_avoidance(ego, conj, rules)
    assert plan.total_delta_v_mps <= 800.0
    assert plan.maneuvers[0].epoch.as_utc_datetime() < tca
