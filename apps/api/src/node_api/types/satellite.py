"""Satellite physical models, state estimates, and operational volumes."""

from __future__ import annotations

from node_api.compat_enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from node_api.types.common import Vector3
from node_api.types.frames import Frame
from node_api.types.state import Covariance6x6, KeplerianElements, StateVector
from node_api.types.time import Epoch


class DataQuality(StrEnum):
    """Freshness / trust label for an estimated satellite state."""

    NOMINAL = "NOMINAL"
    DEGRADED = "DEGRADED"
    STALE = "STALE"


class ThrusterKind(StrEnum):
    """Propulsion technology class for maneuver planning."""

    CHEMICAL = "CHEMICAL"
    ELECTRIC = "ELECTRIC"
    COLD_GAS = "COLD_GAS"


class Satellite(BaseModel):
    """Registered spacecraft metadata for propagation and conjunction screening."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    norad_id: int | None = Field(default=None, description="Catalog id when known.")
    constellation_id: str
    mass_kg: float = Field(..., gt=0)
    drag_area_m2: float = Field(..., ge=0)
    srp_area_m2: float = Field(..., ge=0)
    drag_coefficient: float = Field(default=2.2, ge=0)
    srp_coefficient: float = Field(default=1.0, ge=0)
    dimensions_m: Vector3 = Field(
        ...,
        description="Body-frame bounding dimensions in meters for collision radius heuristics.",
    )


class SatelliteState(BaseModel):
    """Best estimate of instantaneous state plus resources."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sat_id: str
    state_vector: StateVector
    covariance: Covariance6x6
    fuel_kg: float = Field(..., ge=0)
    last_updated: Epoch
    data_quality: DataQuality


class ThrusterModel(BaseModel):
    """Simplified thruster constraints for impulsive/finite-burn planning."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ThrusterKind
    max_thrust_n: float = Field(..., gt=0)
    isp_s: float = Field(..., gt=0)
    min_burn_duration_s: float = Field(..., ge=0)
    preferred_directions_body: list[Vector3] = Field(
        default_factory=list,
        description="Unit-ish directions in body frame (e.g. primary engine along -X).",
    )


class OperationalElementTolerances(BaseModel):
    """Half-width tolerances on classical elements defining a keep-in box."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    delta_a_km: float = Field(..., ge=0)
    delta_e: float = Field(..., ge=0)
    delta_i_rad: float = Field(..., ge=0)
    delta_raan_rad: float = Field(..., ge=0)
    delta_argp_rad: float = Field(..., ge=0)
    delta_anomaly_rad: float = Field(..., ge=0)


class OperationalBox(BaseModel):
    """Keep-in zone: nominal Keplerian center plus element-wise tolerances."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    center: KeplerianElements
    tolerances: OperationalElementTolerances


class KeepOutSphere(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["sphere"] = "sphere"
    frame: Frame
    center_km: Vector3
    radius_km: float = Field(..., gt=0)


class KeepOutBox(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["box"] = "box"
    frame: Frame
    center_km: Vector3
    half_extents_km: Vector3 = Field(..., description="Half-sizes along frame axes (km).")


class KeepOutEllipsoid(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["ellipsoid"] = "ellipsoid"
    frame: Frame
    center_km: Vector3
    semi_axes_km: Vector3 = Field(..., description="Semi-axes aligned with frame axes (km).")


class KeepOutGeographic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["geographic"] = "geographic"
    min_altitude_m: float
    max_altitude_m: float
    polygon_vertices: list[tuple[float, float]] = Field(
        ...,
        description="Lon/lat pairs in radians, closed or open per operational convention.",
    )


class KeepOutTemporal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["temporal"] = "temporal"
    forbidden_interval_id: str = Field(
        ...,
        description="Reference to a scheduled exclusion (e.g. RF interference window).",
    )


class GeometricScreenResult(BaseModel):
    """Result of evaluating a state against volumetric keep-outs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    compliant: bool
    violated_zone_kinds: list[str] = Field(default_factory=list)


KeepOutZone = (
    KeepOutSphere
    | KeepOutBox
    | KeepOutEllipsoid
    | KeepOutGeographic
    | KeepOutTemporal
)
