"""Conjunction events, screening geometry, and Pc methodology metadata."""

from __future__ import annotations

from node_api.compat_enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from node_api.types.time import Epoch


class PcMethod(StrEnum):
    """Algorithm used to map geometry + uncertainty into Pc."""

    FOSTER = "FOSTER"
    ALFANO = "ALFANO"
    CHAN = "CHAN"
    MONTE_CARLO = "MONTE_CARLO"


class ConjunctionSource(StrEnum):
    """Where the event record originated."""

    CDM = "CDM"
    INTERNAL_SCREENING = "INTERNAL_SCREENING"
    MANUAL = "MANUAL"


class ConjunctionStatus(StrEnum):
    """Operator workflow state for a conjunction."""

    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    MITIGATED = "MITIGATED"
    EXPIRED = "EXPIRED"


class CloseApproach(BaseModel):
    """Geometric close approach without a Pc assessment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    primary_id: str
    secondary_id: str
    tca: Epoch
    miss_distance_km: float = Field(..., ge=0)
    relative_velocity_km_s: float = Field(..., ge=0)
    source: ConjunctionSource
    created_at: Epoch


class Conjunction(BaseModel):
    """Full conjunction record including Pc and lifecycle status."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    primary_id: str
    secondary_id: str
    tca: Epoch
    miss_distance_km: float = Field(..., ge=0)
    relative_velocity_km_s: float = Field(..., ge=0)
    pc: float = Field(..., ge=0, le=1)
    pc_method: PcMethod
    source: ConjunctionSource
    created_at: Epoch
    status: ConjunctionStatus


class CDMResponse(BaseModel):
    """Acknowledgement / disposition payload after operator review of a CDM."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cdm_id: str
    acknowledged_at: Epoch
    operator_id: str
    disposition_note: str | None = None
