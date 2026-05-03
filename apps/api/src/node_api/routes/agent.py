"""LLM agent HTTP endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from node_api.lib.agent.runner import (
    AgentTurnRequest,
    AgentTurnResponse,
    ChatMessage,
    PlanResponse,
    run_agent_turn,
)

router = APIRouter()

__all__ = ["AgentTurnRequest", "AgentTurnResponse", "ChatMessage", "PlanResponse"]


@router.post("/turn", response_model=AgentTurnResponse)
async def agent_turn(body: AgentTurnRequest) -> AgentTurnResponse:
    return run_agent_turn(body)
