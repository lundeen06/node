"""Propagated trajectories and derived event intervals."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from node_api.types.common import Interval
from node_api.types.state import StateVector
from node_api.types.time import Epoch


class TrajectorySample(BaseModel):
    """Single trajectory state along an arc."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    epoch: Epoch
    state: StateVector


class Trajectory(BaseModel):
    """Time-ordered state history or prediction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sat_id: str
    samples: list[TrajectorySample] = Field(..., min_length=2)


class GroundPass(BaseModel):
    """Rise/set window for a satellite above a ground site."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    station_id: str
    sat_id: str
    interval: Interval
    max_elevation_deg: float


class HeatLoadSample(BaseModel):
    """Scalar thermal proxy at an epoch (implementation-defined)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    epoch: Epoch
    average_power_w: float


class RadiationDoseSample(BaseModel):
    """Scalar radiation exposure proxy at an epoch (implementation-defined)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    epoch: Epoch
    ionizing_dose_rad: float


class SunAngleSample(BaseModel):
    """Sun geometry sample for thermal and power budgeting."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    epoch: Epoch
    beta_rad: float = Field(..., description="Sun angle to orbital plane proxy (context-specific).")
    off_nadir_rad: float = Field(..., description="Body-Sun off-pointing angle (mission-defined).")


class EclipseInterval(BaseModel):
    """Umbra/penumbra interval for power and thermal planning."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sat_id: str
    interval: Interval
    eclipse_fraction: float = Field(..., ge=0, le=1)
