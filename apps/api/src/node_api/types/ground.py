"""Ground stations, contacts, and scheduling requests."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from node_api.types.common import Interval
from node_api.types.frames import GeodeticPosition
from node_api.types.time import Epoch


class GroundStation(BaseModel):
    """Fixed ground asset capable of RF contact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    position: GeodeticPosition
    min_elevation_deg: float = Field(default=5.0, ge=0, le=90)


class GroundContact(BaseModel):
    """Scheduled or predicted contact interval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    station_id: str
    sat_id: str
    interval: Interval
    predicted_data_volume_mbits: float | None = None


class ContactRequest(BaseModel):
    """Operator intent to reserve uplink/downlink for a window."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    station_id: str
    sat_id: str
    requested_interval: Interval
    priority: int = Field(default=0, description="Higher wins conflicts in planning stubs.")
    created_at: Epoch
