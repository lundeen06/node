"""Pydantic models construct with minimal valid examples."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

from node_api.types.approval import (
    ApprovalRecord,
    AuditEntry,
    AuthMethod,
    OperatorDecision,
    OperatorDecisionKind,
)
from node_api.types.catalog import (
    CDM,
    OEM,
    TLE,
    CatalogObject,
    CDMParticipant,
    EOPParams,
    ObjectType,
    OEMHeader,
    OEMStateSample,
    RcsSize,
    SpaceWeatherState,
)
from node_api.types.common import Interval, Matrix3x3, Matrix6x6, Vector3
from node_api.types.conjunction import (
    CDMResponse,
    CloseApproach,
    Conjunction,
    ConjunctionSource,
    ConjunctionStatus,
    PcMethod,
)
from node_api.types.constellation import ConstellationConfig, ConstellationSlot, HouseRules
from node_api.types.frames import Frame, GeodeticPosition
from node_api.types.ground import ContactRequest, GroundContact, GroundStation
from node_api.types.maneuver import (
    AttitudeProfileStub,
    BurnFrame,
    ContinuousManeuver,
    FiniteBurn,
    Maneuver,
    ManeuverId,
    ManeuverPlan,
    PlanOrigin,
    ThrustProfileStub,
    ValidationOutcome,
)
from node_api.types.satellite import (
    DataQuality,
    GeometricScreenResult,
    KeepOutSphere,
    OperationalBox,
    OperationalElementTolerances,
    Satellite,
    SatelliteState,
    ThrusterKind,
    ThrusterModel,
)
from node_api.types.state import Covariance6x6, EquinoctialElements, KeplerianElements, StateVector
from node_api.types.time import Epoch, TimeScale
from node_api.types.trajectory import (
    EclipseInterval,
    GroundPass,
    HeatLoadSample,
    RadiationDoseSample,
    SunAngleSample,
    Trajectory,
    TrajectorySample,
)
from node_api.types.workflow import (
    CanvasViewport,
    ExecutionPolicy,
    WorkflowBundle,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowLiteralInput,
    WorkflowNode,
    WorkflowRefInput,
)


def _epoch(offset_hours: float = 0.0) -> Epoch:
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC) + timedelta(hours=offset_hours)
    return Epoch(instant=base, scale=TimeScale.UTC)


def _vec3() -> Vector3:
    return Vector3(data=np.array([7000.0, 0.0, 0.0], dtype=np.float64))


def _vel() -> Vector3:
    return Vector3(data=np.array([0.0, 7.5, 0.0], dtype=np.float64))


def _psd6() -> Matrix6x6:
    diag = np.diag([1.0, 1.0, 1.0, 1e-6, 1e-6, 1e-6]).astype(np.float64)
    return Matrix6x6(data=diag)


def _state() -> StateVector:
    return StateVector(
        position_km=_vec3(),
        velocity_km_s=_vel(),
        epoch=_epoch(),
        frame=Frame.ECI_J2000,
    )


def test_common_and_interval() -> None:
    Vector3(data=np.array([1.0, 0.0, 0.0], dtype=np.float64))
    Matrix3x3(data=np.eye(3, dtype=np.float64))
    _psd6()
    Interval(start=_epoch(0), end=_epoch(1))


def test_state_and_covariance() -> None:
    s = _state()
    Covariance6x6(matrix=_psd6(), epoch=s.epoch, frame=s.frame)
    KeplerianElements(
        semi_major_axis_km=7000.0,
        eccentricity=1e-3,
        inclination_rad=0.01,
        raan_rad=0.2,
        arg_perigee_rad=0.3,
        true_anomaly_rad=0.4,
    )
    EquinoctialElements(
        semi_parameter_km=7000.0,
        f=1e-4,
        g=1e-4,
        h=1e-4,
        k=1e-4,
        mean_longitude_rad=0.5,
    )


def test_satellite_and_zones() -> None:
    Satellite(
        id="SAT-1",
        name="Demo",
        norad_id=25544,
        constellation_id="DEMO",
        mass_kg=250.0,
        drag_area_m2=1.0,
        srp_area_m2=2.0,
        dimensions_m=Vector3(data=np.array([2.0, 2.0, 2.0], dtype=np.float64)),
    )
    s = _state()
    cov = Covariance6x6(matrix=_psd6(), epoch=s.epoch, frame=s.frame)
    SatelliteState(
        sat_id="SAT-1",
        state_vector=s,
        covariance=cov,
        fuel_kg=40.0,
        last_updated=_epoch(),
        data_quality=DataQuality.NOMINAL,
    )
    ThrusterModel(
        kind=ThrusterKind.CHEMICAL,
        max_thrust_n=200.0,
        isp_s=280.0,
        min_burn_duration_s=2.0,
    )
    center = KeplerianElements(
        semi_major_axis_km=7000.0,
        eccentricity=0.001,
        inclination_rad=0.02,
        raan_rad=0.1,
        arg_perigee_rad=0.2,
        mean_anomaly_rad=0.3,
    )
    OperationalBox(
        center=center,
        tolerances=OperationalElementTolerances(
            delta_a_km=5.0,
            delta_e=1e-3,
            delta_i_rad=0.001,
            delta_raan_rad=0.001,
            delta_argp_rad=0.001,
            delta_anomaly_rad=0.001,
        ),
    )
    KeepOutSphere(
        frame=Frame.ECI_J2000,
        center_km=_vec3(),
        radius_km=50.0,
    )
    GeometricScreenResult(compliant=True)


def test_catalog_and_cdm() -> None:
    st = _state()
    cov = Covariance6x6(matrix=_psd6(), epoch=st.epoch, frame=st.frame)
    part = CDMParticipant(norad_id=12345, name="DEB", state=st, covariance=cov)
    CDM(
        id="CDM-1",
        creation_epoch=_epoch(),
        tca=_epoch(2),
        miss_distance_m=500.0,
        relative_velocity_m_s=14.0,
        primary=part,
        secondary=part,
        pc=1e-4,
        originator="TEST",
    )
    TLE(
        line1="1 25544U 98067A   24001.50000000  .00002100  00000-0  12345-0 0  9990",
        line2="2 25544  51.6400  12.0000 0001234  90.0000 270.0000 15.50000000 12345",
        epoch=_epoch(),
        satellite_number=25544,
    )
    OEM(
        header=OEMHeader(
            object_id="SAT-1",
            object_name="Demo",
            originator="NODE",
            reference_frame=Frame.ECI_J2000,
        ),
        samples=[OEMStateSample(epoch=_epoch(), state=_state())],
    )
    SpaceWeatherState(epoch=_epoch(), kp=2.0, ap=8.0, f10_7=120.0)
    EOPParams(epoch=_epoch(), xp_arcsec=0.05, yp_arcsec=0.12, ut1_utc_s=-0.12, lod_s=0.0005)
    CatalogObject(
        norad_id=99999,
        name="OBJ",
        object_type=ObjectType.DEBRIS,
        rcs_size=RcsSize.SMALL,
        latest_state=_state(),
        source="TEST",
    )


def test_conjunction_and_maneuver_workflow() -> None:
    CloseApproach(
        id="CA-1",
        primary_id="SAT-1",
        secondary_id="DEB-1",
        tca=_epoch(3),
        miss_distance_km=0.5,
        relative_velocity_km_s=14.0,
        source=ConjunctionSource.INTERNAL_SCREENING,
        created_at=_epoch(),
    )
    Conjunction(
        id="CJ-1",
        primary_id="SAT-1",
        secondary_id="DEB-1",
        tca=_epoch(3),
        miss_distance_km=0.5,
        relative_velocity_km_s=14.0,
        pc=1e-4,
        pc_method=PcMethod.FOSTER,
        source=ConjunctionSource.CDM,
        created_at=_epoch(),
        status=ConjunctionStatus.NEW,
    )
    CDMResponse(cdm_id="CDM-1", acknowledged_at=_epoch(), operator_id="OP-1")
    st = _state()
    dv = Vector3(data=np.array([0.05, 0.0, 0.0], dtype=np.float64))
    m = Maneuver(epoch=_epoch(1), delta_v=dv, frame=BurnFrame.RIC)
    ManeuverPlan(
        sat_id="SAT-1",
        maneuvers=[m],
        total_delta_v_mps=0.05,
        total_fuel_kg=0.1,
        objective="demo",
        predicted_post_state=st,
        generated_by=PlanOrigin.AGENT,
        generated_at=_epoch(2),
        validation_results=[ValidationOutcome(check_id="FUEL", passed=True, message="ok")],
    )
    FiniteBurn(
        start_epoch=_epoch(),
        duration_s=30.0,
        thrust_profile=ThrustProfileStub(profile_id="TP-1"),
        attitude_profile=AttitudeProfileStub(profile_id="AP-1"),
    )
    ContinuousManeuver(
        start_epoch=_epoch(0),
        end_epoch=_epoch(1),
        thrust_profile=ThrustProfileStub(profile_id="TP-2"),
        attitude_profile=AttitudeProfileStub(profile_id="AP-2"),
    )
    policy = ExecutionPolicy(
        auto_execute_below_dv_mps=0.01,
        require_approval_above_dv_mps=0.05,
    )
    node = WorkflowNode(
        id="n1",
        function_ref="node_api.lib.solvers.avoidance.solve_impulsive_avoidance",
        inputs={
            "threat": WorkflowRefInput(kind="ref", ref="ingest.event"),
            "margin": WorkflowLiteralInput(kind="literal", value=1e-4),
        },
        position=(120.0, 80.0),
    )
    WorkflowGraph(
        id="WF-1",
        name="demo",
        nodes=[node],
        edges=[WorkflowEdge(from_node="n0", from_output="x", to_node="n1", to_input="threat")],
        execution_policy=policy,
    )
    WorkflowBundle(graph=WorkflowGraph(id="WF-2", name="x", nodes=[node], execution_policy=policy))
    CanvasViewport()
    ManeuverId("queued-1")


def test_trajectory_ground_constellation_approval() -> None:
    st = _state()
    Trajectory(
        sat_id="SAT-1",
        samples=[
            TrajectorySample(epoch=_epoch(0), state=st),
            TrajectorySample(epoch=_epoch(1), state=st),
        ],
    )
    GroundPass(
        station_id="GS-1",
        sat_id="SAT-1",
        interval=Interval(start=_epoch(0), end=_epoch(0.5)),
        max_elevation_deg=45.0,
    )
    EclipseInterval(
        sat_id="SAT-1",
        interval=Interval(start=_epoch(0), end=_epoch(0.2)),
        eclipse_fraction=1.0,
    )
    SunAngleSample(epoch=_epoch(), beta_rad=0.1, off_nadir_rad=0.05)
    HeatLoadSample(epoch=_epoch(), average_power_w=120.0)
    RadiationDoseSample(epoch=_epoch(), ionizing_dose_rad=0.001)
    GroundStation(
        id="GS-1",
        name="Demo GS",
        position=GeodeticPosition(latitude_rad=0.7, longitude_rad=-1.3, altitude_m=100.0),
    )
    GroundContact(
        station_id="GS-1",
        sat_id="SAT-1",
        interval=Interval(start=_epoch(0), end=_epoch(0.1)),
    )
    ContactRequest(
        id="CR-1",
        station_id="GS-1",
        sat_id="SAT-1",
        requested_interval=Interval(start=_epoch(2), end=_epoch(2.1)),
        created_at=_epoch(),
    )
    ConstellationConfig(
        id="CONST-1",
        name="demo",
        member_sat_ids=["SAT-1"],
        slots=[ConstellationSlot(slot_id="S1", plane_id="P1", phasing_index=0)],
    )
    HouseRules(
        constellation_id="CONST-1",
        max_auto_delta_v_mps=0.02,
        pc_mitigation_threshold=1e-4,
    )
    ApprovalRecord(
        operator_id="OP-1",
        approved_at=_epoch(),
        plan_id="PLAN-1",
        edits_applied=[],
        authentication_method=AuthMethod.MFA,
    )
    OperatorDecision(
        operator_id="OP-1",
        decision=OperatorDecisionKind.APPROVE,
        plan_id="PLAN-1",
        timestamp=_epoch(),
    )
    AuditEntry(
        id="AUD-1",
        timestamp=_epoch(),
        actor_id="OP-1",
        actor_type="OPERATOR",
        action="APPROVE_PLAN",
        payload_summary="plan PLAN-1",
    )
