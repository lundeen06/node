"""External catalog objects, TLE/OEM/CDM products, space weather, and EOP parameters."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from node_api.types.frames import Frame
from node_api.types.state import Covariance6x6, StateVector
from node_api.types.time import Epoch


class ObjectType(StrEnum):
    """High-level RSO classification."""

    PAYLOAD = "PAYLOAD"
    ROCKET_BODY = "ROCKET_BODY"
    DEBRIS = "DEBRIS"
    UNKNOWN = "UNKNOWN"


class RcsSize(StrEnum):
    """Radar cross-section bucket from catalog metadata."""

    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"


class CatalogObject(BaseModel):
    """Screenable resident space object with latest state snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    norad_id: int
    name: str
    object_type: ObjectType
    rcs_size: RcsSize
    country: str | None = None
    launch_date: Epoch | None = None
    latest_state: StateVector
    source: str = Field(..., description="Catalog or OEM origin label.")


class TLE(BaseModel):
    """Two-line element set for SGP4-class propagation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    line1: str
    line2: str
    epoch: Epoch = Field(..., description="TLE epoch (B* epoch line).")
    satellite_number: int = Field(..., description="Same family as NORAD catalog id.")

    def to_state_vector(self) -> StateVector:
        """Placeholder: will parse TLE and produce a TEME/J2000 state at epoch."""
        raise NotImplementedError


class OEMHeader(BaseModel):
    """Minimal OEM metadata block (CCSDS-style, not full grammar)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    object_id: str
    object_name: str
    originator: str
    reference_frame: Frame
    time_scale: str = Field(default="UTC", description="OEM time system label.")


class OEMStateSample(BaseModel):
    """Single OEM state sample."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    epoch: Epoch
    state: StateVector


class OEM(BaseModel):
    """Orbit Ephemeris Message content as header + time series."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    header: OEMHeader
    samples: list[OEMStateSample] = Field(..., min_length=1)


class CDMParticipant(BaseModel):
    """Per-object geometry in a CDM."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    norad_id: int | None
    name: str
    state: StateVector
    covariance: Covariance6x6


class CDM(BaseModel):
    """Conjunction Data Message — canonical conjunction warning payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    creation_epoch: Epoch
    tca: Epoch
    miss_distance_m: float = Field(..., ge=0)
    relative_velocity_m_s: float = Field(..., ge=0)
    primary: CDMParticipant
    secondary: CDMParticipant
    pc: float | None = Field(default=None, ge=0, le=1)
    originator: str


class SpaceWeatherState(BaseModel):
    """NOAA/SWPC-style indices snapshot for drag and charging awareness."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    epoch: Epoch
    kp: float = Field(..., ge=0)
    ap: float = Field(..., ge=0)
    f10_7: float = Field(..., ge=0, description="Solar flux at 10.7 cm.")
    solar_flux: float | None = Field(default=None, ge=0)
    geomagnetic_storm_level: str | None = Field(
        default=None,
        description="Qualitative storm label when issued (e.g. G-scale).",
    )


class EOPParams(BaseModel):
    """Earth orientation parameter bundle for high-precision frame transforms."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    epoch: Epoch
    xp_arcsec: float
    yp_arcsec: float
    ut1_utc_s: float
    lod_s: float = Field(..., description="Length of day offset seconds.")
