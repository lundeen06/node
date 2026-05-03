"""Agentic loop using the OpenAI SDK with function-calling tool use.

Defines the HTTP-wire request/response types used by routes/agent.py.
"""

from __future__ import annotations

import json
from typing import Any, Literal, cast

import openai
from pydantic import BaseModel, ConfigDict, Field

from node_api.config import settings
from node_api.lib.agent.prompts import SYSTEM_PROMPT
from node_api.lib.agent.schemas import OPENAI_CHAT_TOOLS
from node_api.lib.agent.tools import TOOL_REGISTRY

# ---------------------------------------------------------------------------
# Wire types (JSON-native; no numpy)
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant", "system"]
    content: str


class ConjunctionContextWire(BaseModel):
    """Optional conjunction the operator focused in the UI (epoch + pair from live screening)."""

    model_config = ConfigDict(extra="forbid")

    conjunction_id: str | None = None
    primary_sat_id: str | None = None
    secondary_sat_id: str | None = None
    tca_utc: str | None = None
    miss_distance_km: float | None = None
    pc_heuristic: float | None = None
    source: str | None = None


class AgentTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    operator_id: str
    messages: list[ChatMessage] = Field(..., min_length=1)
    focus_sat_id: str | None = Field(
        default=None,
        description="Optional spacecraft context for tool routing.",
    )
    conjunction_context: ConjunctionContextWire | None = Field(
        default=None,
        description="Screening event selected in the ops UI (TCA and pair IDs for this turn).",
    )


class DeltaVMps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    z: float


class ManeuverResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    epoch_utc: str
    delta_v_mps: DeltaVMps
    frame: str
    duration_s: float | None = None


class PlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    sat_id: str
    maneuvers: list[ManeuverResponse]
    total_delta_v_mps: float
    objective: str
    generated_by: str = "AGENT"
    validation_passed: bool = True


class AgentTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assistant_message: str
    proposed_plans: list[PlanResponse] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _execute_tool(name: str, arguments_json: str) -> dict[str, Any]:
    try:
        inputs: dict[str, Any] = json.loads(arguments_json)
    except json.JSONDecodeError:
        return {"error": f"Invalid JSON arguments for tool {name}"}
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(**inputs)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def _assistant_message_for_api(msg: Any) -> dict[str, Any]:
    """Build assistant history dict without SDK-only keys (avoids OpenAI 400 on follow-up turns)."""
    out: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        serialized: list[dict[str, Any]] = []
        for tc in tool_calls:
            fn = tc.function
            serialized.append(
                {
                    "id": tc.id,
                    "type": getattr(tc, "type", None) or "function",
                    "function": {"name": fn.name, "arguments": fn.arguments},
                },
            )
        out["tool_calls"] = serialized
    return out


def _plan_dict_to_response(plan: dict[str, Any]) -> PlanResponse:
    maneuvers = [
        ManeuverResponse(
            epoch_utc=m["epoch_utc"],
            delta_v_mps=DeltaVMps(**m["delta_v_mps"]),
            frame=m["frame"],
            duration_s=m.get("duration_s"),
        )
        for m in plan["maneuvers"]
    ]
    all_passed = all(v["passed"] for v in plan.get("validation", []))
    return PlanResponse(
        plan_id=plan["plan_id"],
        sat_id=plan["sat_id"],
        maneuvers=maneuvers,
        total_delta_v_mps=plan["total_delta_v_mps"],
        objective=plan["objective"],
        generated_by=plan.get("generated_by", "AGENT"),
        validation_passed=all_passed,
    )


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------

_MAX_ROUNDS = 8
_MODEL = "gpt-4o"


def run_agent_turn(request: AgentTurnRequest) -> AgentTurnResponse:
    """Drive the OpenAI function-calling loop until the model produces a final answer."""
    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        raise ValueError(
            "NODE_OPENAI_API_KEY is empty. Set it in apps/api/.env and restart uvicorn.",
        )
    client = openai.OpenAI(api_key=api_key)

    system_content = SYSTEM_PROMPT
    if request.conjunction_context is not None:
        cc = request.conjunction_context
        lines: list[str] = []
        if cc.conjunction_id:
            lines.append(f"Conjunction ID: `{cc.conjunction_id}`")
        if cc.primary_sat_id and cc.secondary_sat_id:
            lines.append(f"Pair: `{cc.primary_sat_id}` vs `{cc.secondary_sat_id}`")
        if cc.tca_utc:
            lines.append(f"TCA (UTC): {cc.tca_utc}")
        if cc.miss_distance_km is not None:
            lines.append(f"Miss distance (km): {cc.miss_distance_km}")
        if cc.pc_heuristic is not None:
            lines.append(f"Screening Pc (heuristic): {cc.pc_heuristic}")
        if cc.source:
            lines.append(f"Data source: {cc.source}")
        if lines:
            system_content += (
                "\n\nOperator-selected conjunction context (treat as authoritative for this turn; "
                "still call get_active_conjunctions to reconcile with the latest persisted snapshot):\n"
                + "\n".join(f"- {ln}" for ln in lines)
            )

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_content}]
    for m in request.messages:
        if m.role != "system":
            messages.append({"role": m.role, "content": m.content})

    produced_plans: list[PlanResponse] = []
    citations: list[str] = []

    for _ in range(_MAX_ROUNDS):
        try:
            response = client.chat.completions.create(
                model=_MODEL,
                messages=cast(Any, messages),
                tools=cast(Any, OPENAI_CHAT_TOOLS),
                tool_choice="auto",
            )
        except openai.APIError as exc:
            raise RuntimeError(f"OpenAI API error: {exc}") from exc

        choice = response.choices[0]
        msg = choice.message

        messages.append(_assistant_message_for_api(msg))

        if not msg.tool_calls:
            final_text = (msg.content or "").strip()
            return AgentTurnResponse(
                assistant_message=final_text,
                proposed_plans=produced_plans,
                citations=citations,
            )

        for tool_call in cast(Any, msg.tool_calls or []):
            result = _execute_tool(tool_call.function.name, tool_call.function.arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                },
            )
            if tool_call.function.name == "plan_collision_avoidance" and "plan" in result:
                produced_plans.append(_plan_dict_to_response(cast(dict[str, Any], result["plan"])))
                try:
                    args = json.loads(tool_call.function.arguments)
                    if cid := args.get("conjunction_id"):
                        citations.append(str(cid))
                except json.JSONDecodeError:
                    pass

    return AgentTurnResponse(
        assistant_message="[Agent reached maximum tool-call rounds without a final answer.]",
        proposed_plans=produced_plans,
        citations=citations,
    )
