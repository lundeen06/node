"""Spacecraft catalog: Space-Track ingest, SQLite persistence, physics propagation."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from node_api.db.models import SpacecraftRow
from node_api.db.session import get_session
from node_api.errors import DataUnavailableError
from node_api.lib.geodesy import eci_m_to_lon_lat_deg
from node_api.lib.ingress.constellation_presets import PRESET_METADATA
from node_api.lib.propagation import propagate_mean_elements_at_times
from node_api.physics_runtime import ensure_physics_importable
from node_api.services.spacecraft_catalog import (
    import_constellation_preset,
    register_and_fetch,
    spacecraft_positions_geojson,
    sync_all_registered,
)

ensure_physics_importable()
from physics.infra.slate import AbsoluteOrbitalElements  # noqa: E402

router = APIRouter()


class SpacecraftRegisterIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    sat_id: str = Field(..., min_length=1, max_length=128)
    name: str = ""
    norad_catalog_id: int = Field(..., gt=0)
    purpose: str = ""


class SpacecraftSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sat_id: str
    name: str
    norad_catalog_id: int
    purpose: str
    ephemeris_epoch_utc: datetime
    updated_at: datetime


class SpacecraftDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sat_id: str
    name: str
    norad_catalog_id: int
    purpose: str
    ephemeris_epoch_utc: datetime
    updated_at: datetime
    tle_line1: str
    tle_line2: str
    oe_vector: list[float]
    gp: dict[str, Any]


class TrajectorySampleOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    epoch_utc: str
    position_km: list[float]
    velocity_km_s: list[float]
    lon_deg: float | None = None
    lat_deg: float | None = None


class TrajectoryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    sat_id: str
    samples: list[TrajectorySampleOut]


class ConstellationPresetOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    description: str
    patterns: list[str]


class ImportConstellationIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    preset: str = Field(..., description="starlink | kuiper | planet | galileo | gps")
    limit: int = Field(default=500, ge=1, le=50_000)
    purpose: str = ""
    sat_id_prefix: str = Field(default="", max_length=64)
    timeout_seconds: float = Field(default=300.0, ge=30.0, le=900.0)


@router.post("/register", response_model=SpacecraftDetail)
def register_spacecraft(body: SpacecraftRegisterIn, session: Session = Depends(get_session)) -> SpacecraftDetail:
    """Fetch latest GP from Space-Track for ``norad_catalog_id`` and upsert the database."""
    try:
        row = register_and_fetch(
            session,
            sat_id=body.sat_id.strip(),
            name=body.name,
            norad_catalog_id=body.norad_catalog_id,
            purpose=body.purpose,
        )
    except DataUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _row_to_detail(row)


@router.post("/sync", response_model=dict[str, int])
def sync_spacecraft(session: Session = Depends(get_session)) -> dict[str, int]:
    """Refresh GP snapshots for every registered spacecraft."""
    try:
        n = sync_all_registered(session)
    except DataUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"updated": n}


@router.get("/", response_model=list[SpacecraftSummary])
def list_spacecraft(session: Session = Depends(get_session)) -> list[SpacecraftRow]:
    return list(session.scalars(select(SpacecraftRow).order_by(SpacecraftRow.sat_id)))


@router.get("/constellation-presets", response_model=list[ConstellationPresetOut])
def list_constellation_presets() -> list[ConstellationPresetOut]:
    """Named Space-Track ``OBJECT_NAME`` pattern bundles (bounded import via ``POST /import-constellation``)."""
    return [
        ConstellationPresetOut(
            id=m.id,
            label=m.label,
            description=m.description,
            patterns=list(m.patterns),
        )
        for m in PRESET_METADATA
    ]


@router.post("/import-constellation", response_model=dict[str, Any])
def import_constellation_bulk(
    body: ImportConstellationIn,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Run GP name-pattern queries for a preset and upsert up to ``limit`` spacecraft.

    Respects Space-Track rate limits: use a modest ``limit``, avoid hammering production.
    """
    try:
        return import_constellation_preset(
            session,
            preset_id=body.preset,
            limit=body.limit,
            purpose=body.purpose,
            sat_id_prefix=body.sat_id_prefix,
            timeout_s=body.timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DataUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/catalog-export", response_model=list[SpacecraftDetail])
def export_catalog_snapshot(session: Session = Depends(get_session)) -> list[SpacecraftDetail]:
    """Full persisted catalog (same payload as ``GET /spacecraft/{{sat_id}}`` per row) for backup or offline use.

    Large when many objects are registered — save with ``curl -o`` or pipe to a file.
    """
    rows = list(session.scalars(select(SpacecraftRow).order_by(SpacecraftRow.sat_id)))
    return [_row_to_detail(r) for r in rows]


@router.get("/map-positions")
def spacecraft_map_positions(
    session: Session = Depends(get_session),
    max_count: Annotated[int, Query(ge=1, le=25_000)] = 20_000,
) -> dict[str, Any]:
    """GeoJSON ``FeatureCollection`` of Points: propagated mean elements → ECI → approximate lon/lat at UTC now.

    Suitable for Mapbox ``geojson`` sources. Cap ``max_count`` for very large catalogs.
    """
    return spacecraft_positions_geojson(session, max_count=max_count)


@router.get("/{sat_id}", response_model=SpacecraftDetail)
def get_spacecraft(
    sat_id: str,
    session: Session = Depends(get_session),
) -> SpacecraftDetail:
    row = session.get(SpacecraftRow, sat_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown spacecraft {sat_id!r}.")
    return _row_to_detail(row)


@router.get("/{sat_id}/trajectory", response_model=TrajectoryOut)
def spacecraft_trajectory(
    sat_id: str,
    session: Session = Depends(get_session),
    duration_minutes: Annotated[float, Query(gt=0, le=24 * 60)] = 90.0,
    step_seconds: Annotated[float, Query(gt=1, le=3600)] = 60.0,
    include_llh: Annotated[bool, Query(description="Include approximate lon/lat for map clients.")] = False,
) -> TrajectoryOut:
    """Propagate stored mean elements with ``physics.propulsion.util_dyn.propagate_oe`` (+ optional J2)."""
    row = session.get(SpacecraftRow, sat_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown spacecraft {sat_id!r}.")
    els = AbsoluteOrbitalElements.from_vector(tuple(json.loads(row.oe_vector_json)))
    now = datetime.now(tz=UTC)
    end = now + timedelta(minutes=duration_minutes)
    times: list[datetime] = []
    t = now
    while t <= end:
        times.append(t)
        t += timedelta(seconds=step_seconds)
    if len(times) < 2:
        times = [now, end]
    traj = propagate_mean_elements_at_times(els, row.ephemeris_epoch_utc, times, row.sat_id, use_j2=True)
    samples: list[TrajectorySampleOut] = []
    for s in traj.samples:
        lon_lat: tuple[float, float] | None = None
        if include_llh:
            lon_lat = eci_m_to_lon_lat_deg(s.state.position_km.data * 1000.0, s.epoch.as_utc_datetime())
        samples.append(
            TrajectorySampleOut(
                epoch_utc=s.epoch.instant.isoformat(),
                position_km=[float(x) for x in s.state.position_km.data.tolist()],
                velocity_km_s=[float(x) for x in s.state.velocity_km_s.data.tolist()],
                lon_deg=lon_lat[0] if lon_lat else None,
                lat_deg=lon_lat[1] if lon_lat else None,
            ),
        )
    return TrajectoryOut(sat_id=traj.sat_id, samples=samples)


def _row_to_detail(row: SpacecraftRow) -> SpacecraftDetail:
    return SpacecraftDetail(
        sat_id=row.sat_id,
        name=row.name,
        norad_catalog_id=row.norad_catalog_id,
        purpose=row.purpose,
        ephemeris_epoch_utc=row.ephemeris_epoch_utc,
        updated_at=row.updated_at,
        tle_line1=row.tle_line1,
        tle_line2=row.tle_line2,
        oe_vector=json.loads(row.oe_vector_json),
        gp=json.loads(row.gp_snapshot_json),
    )
