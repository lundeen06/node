"""LLM agent HTTP endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

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
    try:
        return run_agent_turn(body)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc
