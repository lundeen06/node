"""Satellite state and metadata routes (501 stubs)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from node_api.lib.environment import (
    check_geometric_keep_out,
    find_eclipse_intervals,
    find_ground_passes,
)
from node_api.lib.propagation import propagate_numerical, propagate_sgp4, propagate_with_uncertainty

router = APIRouter()

_LIB_SURFACE = (
    propagate_sgp4,
    propagate_numerical,
    propagate_with_uncertainty,
    find_ground_passes,
    find_eclipse_intervals,
    check_geometric_keep_out,
)


@router.get("/")
async def list_satellites() -> JSONResponse:
    _ = _LIB_SURFACE
    return JSONResponse(status_code=501, content={"detail": "Satellite listing not implemented"})


@router.get("/{sat_id}/state")
async def get_satellite_state(sat_id: str) -> JSONResponse:
    _ = _LIB_SURFACE
    return JSONResponse(
        status_code=501,
        content={"detail": f"Satellite state for {sat_id} not implemented"},
    )
