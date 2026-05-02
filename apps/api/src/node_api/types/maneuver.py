"""Maneuver plans, burns, and planner provenance."""

from __future__ import annotations

from enum import StrEnum
from typing import NewType, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from node_api.types.common import Vector3
from node_api.types.state import StateVector
from node_api.types.time import Epoch

ManeuverId = NewType("ManeuverId", str)


class BurnFrame(StrEnum):
    """Frame in which a Δv vector is expressed."""

    RIC = "RIC"
    VNB = "VNB"
    ECI = "ECI"


class PlanOrigin(StrEnum):
    """Who produced the maneuver plan."""

    AGENT = "AGENT"
    SOLVER = "SOLVER"
    OPERATOR = "OPERATOR"


class ValidationOutcome(BaseModel):
    """Single validation gate result attached to a plan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    passed: bool
    message: str


class Maneuver(BaseModel):
    """Single impulsive or short finite burn modeled as Δv at an epoch."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    epoch: Epoch
    delta_v: Vector3 = Field(
        ...,
        description="Δv vector in m/s along axes implied by ``frame`` (RIC/VNB/ECI).",
    )
    frame: BurnFrame
    duration_s: float | None = Field(
        default=None,
        ge=0,
        description="Optional duration for finite-burn bookkeeping.",
    )


class ManeuverPlan(BaseModel):
    """Sequence of burns with predicted outcome and validation summary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sat_id: str
    maneuvers: list[Maneuver] = Field(..., min_length=1)
    total_delta_v_mps: float = Field(..., ge=0)
    total_fuel_kg: float = Field(..., ge=0)
    objective: str
    predicted_post_state: StateVector
    generated_by: PlanOrigin
    generated_at: Epoch
    validation_results: list[ValidationOutcome] = Field(default_factory=list)


class ThrustProfileStub(BaseModel):
    """Placeholder thrust magnitude profile identifier (realization TBD)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_id: str
    notes: str | None = None


class AttitudeProfileStub(BaseModel):
    """Placeholder attitude schedule identifier (realization TBD)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_id: str
    notes: str | None = None


class FiniteBurn(BaseModel):
    """Non-impulsive burn parameterized by duration and profiles."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start_epoch: Epoch
    duration_s: float = Field(..., gt=0)
    thrust_profile: ThrustProfileStub
    attitude_profile: AttitudeProfileStub


class ContinuousManeuver(BaseModel):
    """Low-thrust or long-duration steering arc (scaffold)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start_epoch: Epoch
    end_epoch: Epoch
    thrust_profile: ThrustProfileStub
    attitude_profile: AttitudeProfileStub

    @model_validator(mode="after")
    def _time_order(self) -> Self:
        if self.end_epoch.as_utc_datetime() <= self.start_epoch.as_utc_datetime():
            msg = "ContinuousManeuver.end_epoch must be after start_epoch."
            raise ValueError(msg)
        return self
