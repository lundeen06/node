"""Conjunction screening routes (501 stubs)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from node_api.lib.conjunction import (
    compute_pc,
    find_close_approach,
    screen_catalog_against_ego,
    screen_constellation,
)
from node_api.lib.ingress.space_track import fetch_cdm, fetch_tle

router = APIRouter()

_LIB_SURFACE = (fetch_tle, fetch_cdm, find_close_approach, compute_pc, screen_catalog_against_ego, screen_constellation)


@router.get("/")
async def list_conjunctions() -> JSONResponse:
    _ = _LIB_SURFACE
    return JSONResponse(status_code=501, content={"detail": "Conjunction listing not implemented"})


@router.get("/{conjunction_id}")
async def get_conjunction(conjunction_id: str) -> JSONResponse:
    _ = _LIB_SURFACE
    return JSONResponse(
        status_code=501,
        content={"detail": f"Conjunction {conjunction_id} not implemented"},
    )
