"""Maneuver planning routes (501 stubs)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from node_api.lib.actions import queue_maneuver
from node_api.lib.mission.collision_avoidance import plan_collision_avoidance
from node_api.lib.solvers.avoidance import solve_impulsive_avoidance, solve_optimal_avoidance_timing
from node_api.lib.validation import (
    check_fuel_compliance,
    check_induced_conjunctions,
    check_keep_out_compliance,
)

router = APIRouter()

_LIB_SURFACE = (
    plan_collision_avoidance,
    solve_impulsive_avoidance,
    solve_optimal_avoidance_timing,
    check_induced_conjunctions,
    check_keep_out_compliance,
    check_fuel_compliance,
    queue_maneuver,
)


@router.post("/plans")
async def create_maneuver_plan() -> JSONResponse:
    _ = _LIB_SURFACE
    return JSONResponse(status_code=501, content={"detail": "Maneuver plan creation not implemented"})


@router.get("/plans/{plan_id}")
async def get_maneuver_plan(plan_id: str) -> JSONResponse:
    _ = _LIB_SURFACE
    return JSONResponse(status_code=501, content={"detail": f"Plan {plan_id} not implemented"})
