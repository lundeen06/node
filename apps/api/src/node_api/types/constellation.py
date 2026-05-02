"""Constellation topology and operator policy ("house rules")."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from node_api.types.satellite import KeepOutZone, OperationalBox


class ConstellationSlot(BaseModel):
    """Named orbital slot / plane assignment within a constellation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slot_id: str
    plane_id: str
    phasing_index: int = Field(..., ge=0)


class ConstellationConfig(BaseModel):
    """Fleet-level registration and slotting."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    member_sat_ids: list[str] = Field(..., min_length=1)
    slots: list[ConstellationSlot] = Field(default_factory=list)


class HouseRules(BaseModel):
    """Operator-specific safety and automation bounds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    constellation_id: str
    max_auto_delta_v_mps: float = Field(..., ge=0)
    pc_mitigation_threshold: float = Field(..., ge=0, le=1)
    operational_boxes: dict[str, OperationalBox] = Field(
        default_factory=dict,
        description="sat_id → keep-in volume.",
    )
    keep_out_zones: list[KeepOutZone] = Field(default_factory=list)
