"""LLM agent HTTP sketch — request/response shapes only."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from node_api.types.maneuver import ManeuverPlan

router = APIRouter()


class ChatMessage(BaseModel):
    """Single turn in an operator ↔ agent conversation."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant", "system"]
    content: str


class AgentTurnRequest(BaseModel):
    """Body for ``POST /agent/turn`` — drives tool use in production."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    operator_id: str
    messages: list[ChatMessage] = Field(..., min_length=1)
    focus_sat_id: str | None = Field(
        default=None,
        description="Optional spacecraft context for tool routing.",
    )


class AgentTurnResponse(BaseModel):
    """Assistant reply plus structured artifacts for UI diffing."""

    model_config = ConfigDict(extra="forbid")

    assistant_message: str
    proposed_plans: list[ManeuverPlan] = Field(default_factory=list)
    citations: list[str] = Field(
        default_factory=list,
        description="Traceability strings (CDM ids, OEM hashes, etc.).",
    )


@router.post("/turn")
async def agent_turn(_body: AgentTurnRequest) -> JSONResponse:
    _ = (AgentTurnResponse, ManeuverPlan)
    return JSONResponse(
        status_code=501,
        content={"detail": "Agent inference endpoint not implemented"},
    )
