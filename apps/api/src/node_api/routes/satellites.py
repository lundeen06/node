"""Satellite state and metadata routes."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from node_api.errors import DataUnavailableError
from node_api.lib.environment import (
    check_geometric_keep_out,
    find_eclipse_intervals,
    find_ground_passes,
)
from node_api.lib.ingress.gp_elements import gp_record_to_tle
from node_api.lib.ingress.space_track import fetch_gp_rows
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


class TlePayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    satellite_number: int
    line1: str
    line2: str
    epoch_utc: str = Field(..., description="TLE epoch as ISO 8601 UTC.")


class SpaceTrackGpItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    norad_catalog_id: int
    tle: TlePayload
    gp: dict[str, Any] = Field(
        ...,
        description="Raw Space-Track gp-class fields (OBJECT_NAME, MEAN_MOTION, EPOCH, …).",
    )


class SpaceTrackGpResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[SpaceTrackGpItem]


def _build_spacetrack_response(norad_ids: list[int]) -> SpaceTrackGpResponse:
    rows = fetch_gp_rows(norad_ids)
    items: list[SpaceTrackGpItem] = []
    for row in rows:
        tle = gp_record_to_tle(row)
        items.append(
            SpaceTrackGpItem(
                norad_catalog_id=tle.satellite_number,
                tle=TlePayload(
                    satellite_number=tle.satellite_number,
                    line1=tle.line1,
                    line2=tle.line2,
                    epoch_utc=tle.epoch.instant.isoformat(),
                ),
                gp=row,
            ),
        )
    return SpaceTrackGpResponse(items=items)


@router.get("/tles", response_model=SpaceTrackGpResponse)
async def get_spacetrack_tles(
    norad_ids: Annotated[
        str,
        Query(
            description=(
                "Comma-separated NORAD catalog IDs. Example: `25544` (ISS), `48274` (Starlink). "
                "See Space-Track gp class fields for what comes back in each `gp` object."
            ),
        ),
    ],
) -> SpaceTrackGpResponse:
    """Fetch latest Space-Track **gp** element sets and parsed TLE lines.

    **Filtering:** this HTTP endpoint only filters by NORAD id list. For arbitrary Space-Track
    predicates (epoch windows, object type, etc.), use :func:`node_api.lib.ingress.space_track.query_gp`
    from Python (see Space-Track REST API docs — predicate chain between ``gp/`` and ``/format/json``).

    **Using the payload:** use ``tle.line1`` / ``tle.line2`` with SGP4 (e.g. :func:`propagate_sgp4`);
    ``gp`` carries metadata such as ``OBJECT_NAME``, ``EPOCH``, ``MEAN_MOTION``, ``INCLINATION``, etc.
    """
    parts = [p.strip() for p in norad_ids.split(",") if p.strip()]
    if not parts:
        raise HTTPException(status_code=400, detail="Provide at least one NORAD id in norad_ids.")
    try:
        ids = [int(p) for p in parts]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="norad_ids must be integers.") from exc
    try:
        return await asyncio.to_thread(_build_spacetrack_response, ids)
    except DataUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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
