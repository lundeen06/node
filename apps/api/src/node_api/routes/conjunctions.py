"""Conjunction screening routes."""

from __future__ import annotations

from datetime import UTC, datetime, timezone

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field, model_validator

from node_api.lib.ingress.space_track import fetch_cdm, fetch_tle
from node_api.lib.pair_conjunction_keplerian import (
    KeplerianPairKeepoutResult,
    screen_pair_keplerian_keepout,
)
from node_api.db.session import get_session
from node_api.lib.pair_conjunction_sgp4 import screen_pair_sphere_sgp4
from node_api.services.catalog_conjunction_screen import screen_catalog_close_approaches
from node_api.services.conjunction_demo_pair_seed import refresh_demo_pair_for_sim_utc
from node_api.services.conjunction_store import replace_catalog_conjunction_snapshot
from node_api.types.state import KeplerianElements
from node_api.types.time import Epoch, TimeScale

router = APIRouter()

# Keplerian keep-out screening (canonical implementation in ``pair_conjunction_keplerian``).
evaluate_keplerian_pair_conjunction_keepout = screen_pair_keplerian_keepout

_LIB_SURFACE = (fetch_tle, fetch_cdm)


class TleLines(BaseModel):
    model_config = ConfigDict(frozen=True)

    line1: str = Field(..., description="TLE line 1")
    line2: str = Field(..., description="TLE line 2")


class PairSphereScreenRequest(BaseModel):
    """SGP4 pairwise screening with ego-centered sphere."""

    model_config = ConfigDict(frozen=True)

    my_spacecraft: TleLines = Field(..., description="Ego satellite TLE (sphere centered here).")
    external_spacecraft: TleLines = Field(..., description="Secondary / threat object TLE.")
    start_utc: datetime = Field(..., description="Propagation start (timezone-aware).")
    sphere_radius_km: float = Field(default=10.0, gt=0, description="Keep-out sphere radius (km).")
    step_s: float = Field(default=30.0, gt=0, description="Sample interval for both vehicles (s).")
    search_max_orbits: int = Field(
        default=30,
        ge=1,
        le=500,
        description="Minimum search horizon in ego orbital periods before declaring no penetration.",
    )
    followup_orbits: int = Field(
        default=5,
        ge=1,
        le=100,
        description="After first sphere entry, extend integration by this many ego orbits.",
    )
    weight_distance: float = Field(default=0.5, ge=0, description="Weight on proximity score in heuristic P.")
    weight_time: float = Field(default=0.5, ge=0, description="Weight on dwell score in heuristic P.")


class KeplerianPairKeepoutRequest(BaseModel):
    """Classical elements for both objects + horizon + ego-centered keep-out sphere."""

    model_config = ConfigDict(frozen=True)

    my_spacecraft: KeplerianElements = Field(..., description="Ego satellite (sphere centered here).")
    external_spacecraft: KeplerianElements = Field(..., description="Secondary object.")
    start_utc: datetime = Field(..., description="Screening start (timezone-aware).")
    horizon_duration_s: float = Field(..., gt=0, description="Forward propagation length (s).")
    keep_out_sphere_radius_km: float = Field(..., gt=0, description="Keep-out radius around ego (km).")
    step_s: float = Field(default=30.0, gt=0, description="Sample step for both trajectories (s).")
    weight_distance: float = Field(default=0.5, ge=0, description="Weight on proximity term per sample.")
    weight_time: float = Field(default=0.5, ge=0, description="Weight on in-sphere dwell per sample.")
    use_j2: bool = Field(default=False, description="If true, use ``util_dyn`` J2 mean-element rates.")


class KeplerianPairKeepoutResponse(BaseModel):
    conjunction_occurred: bool
    first_conjunction_utc: datetime | None = None
    conjunction_score_normalized: float = Field(
        ...,
        ge=0,
        le=1,
        description="Mean per-timestep weighted score: sum_i(w_d·prox_i + w_t·dwell_i) / N.",
    )
    closest_approach_km: float = Field(..., ge=0)
    time_points_inside_sphere: int = Field(..., ge=0)
    total_time_points: int = Field(..., ge=0)
    integration_start_utc: datetime
    integration_end_utc: datetime
    step_s: float
    horizon_duration_s: float
    keep_out_sphere_radius_km: float
    weight_distance_applied: float
    weight_time_applied: float
    notes: str = Field(
        default="Mean-element propagation (``propagate_oe`` / ``oe_to_pv``). Score is not CDM Pc.",
        description="Method legend.",
    )


class CatalogScreenManeuverBurnIn(BaseModel):
    """ECI Δv burn for optional catalog-screen refinement (same physics as trajectory-preview)."""

    model_config = ConfigDict(frozen=True)

    epoch_utc: datetime
    delta_v_mps: dict[str, float]
    frame: str = "ECI"


class CatalogScreenRequest(BaseModel):
    """Screen catalog pairs near ``sim_utc`` (demo / ops visualization)."""

    model_config = ConfigDict(frozen=True)

    sim_utc: datetime = Field(..., description="Simulation epoch for screening (timezone-aware UTC).")
    separation_prefilter_km: float = Field(default=4000.0, gt=0, le=50_000.0)
    max_satellites: int = Field(default=80, ge=2, le=500)
    max_candidate_pairs: int = Field(default=2500, ge=1, le=50_000)
    sphere_radius_km: float = Field(default=10.0, gt=0, le=500.0)
    step_s: float = Field(default=90.0, gt=1, le=600.0)
    search_max_orbits: int = Field(default=2, ge=1, le=30)
    maneuver_preview_sat_id: str | None = Field(
        default=None,
        description="If set with maneuvers, re-evaluate hits involving this sat at TCA using preview trajectory.",
    )
    maneuver_preview_maneuvers: list[CatalogScreenManeuverBurnIn] | None = Field(
        default=None,
        description="ECI-frame impulsive burns; catalog TLEs are not updated.",
    )

    @model_validator(mode="after")
    def _maneuver_preview_consistency(self) -> CatalogScreenRequest:
        sat = self.maneuver_preview_sat_id
        mans = self.maneuver_preview_maneuvers
        if mans and not (sat and sat.strip()):
            msg = "maneuver_preview_maneuvers requires maneuver_preview_sat_id."
            raise ValueError(msg)
        return self


class CatalogScreenEventOut(BaseModel):
    id: str
    primary_sat_id: str
    secondary_sat_id: str
    tca_utc: str
    miss_distance_km: float
    pc_heuristic: float
    sphere_radius_km: float
    eci_mid_m: list[float] = Field(..., min_length=3, max_length=3)
    primary_eci_m: list[float] = Field(..., min_length=3, max_length=3)
    secondary_eci_m: list[float] = Field(..., min_length=3, max_length=3)


class CatalogScreenResponse(BaseModel):
    sim_utc: str
    events: list[CatalogScreenEventOut]


class PairSphereScreenResponse(BaseModel):
    conjunction_occurred: bool
    conjunction_probability_heuristic: float = Field(..., ge=0, le=1)
    closest_approach_km: float = Field(..., ge=0)
    first_entry_utc: datetime | None = None
    my_orbital_period_s: float = Field(..., gt=0)
    time_points_inside_sphere: int = Field(..., ge=0)
    total_time_points: int = Field(..., ge=0)
    time_spent_inside_s: float = Field(..., ge=0)
    integration_start_utc: datetime
    integration_end_utc: datetime
    step_s: float
    sphere_radius_km: float
    weight_distance_applied: float
    weight_time_applied: float
    notes: str = Field(
        default="probability_heuristic blends proximity and dwell; not a CDM Monte Carlo Pc.",
        description="Method legend.",
    )


@router.post("/catalog-screen", response_model=CatalogScreenResponse)
def catalog_screen(
    body: CatalogScreenRequest,
    session: Session = Depends(get_session),
) -> CatalogScreenResponse:
    """SGP4 pairwise screening across a catalog subset (prefilter + keep-out sphere)."""
    if body.sim_utc.tzinfo is None:
        raise HTTPException(status_code=400, detail="sim_utc must be timezone-aware.")
    sim = body.sim_utc.astimezone(UTC)
    # Keep the synthetic demo pair anchored near sim_utc so SGP4 J2 RAAN drift hasn't yet
    # separated the 45/50 inclination planes by the time screening runs (the pair is
    # otherwise temporally fragile; see conjunction_demo_pair_seed for details).
    refresh_demo_pair_for_sim_utc(session, sim)
    maneuver_preview: tuple[str, list[tuple[datetime, np.ndarray]]] | None = None
    if body.maneuver_preview_sat_id and body.maneuver_preview_maneuvers:
        sid = body.maneuver_preview_sat_id.strip()
        burns: list[tuple[datetime, np.ndarray]] = []
        for m in body.maneuver_preview_maneuvers:
            if str(m.frame).upper() != "ECI":
                raise HTTPException(
                    status_code=400,
                    detail="Catalog maneuver preview supports ECI-frame burns only.",
                )
            dv = m.delta_v_mps
            arr = np.array(
                [float(dv["x"]), float(dv["y"]), float(dv["z"])],
                dtype=np.float64,
            )
            burns.append((m.epoch_utc.astimezone(UTC), arr))
        if burns:
            maneuver_preview = (sid, burns)
    raw = screen_catalog_close_approaches(
        session,
        sim_utc=sim,
        separation_prefilter_km=body.separation_prefilter_km,
        max_satellites=body.max_satellites,
        max_candidate_pairs=body.max_candidate_pairs,
        sphere_radius_km=body.sphere_radius_km,
        step_s=body.step_s,
        search_max_orbits=body.search_max_orbits,
        maneuver_preview=maneuver_preview,
    )
    replace_catalog_conjunction_snapshot(session, raw)
    session.commit()
    events = [
        CatalogScreenEventOut(
            id=e["id"],
            primary_sat_id=e["primary_sat_id"],
            secondary_sat_id=e["secondary_sat_id"],
            tca_utc=e["tca_utc"],
            miss_distance_km=e["miss_distance_km"],
            pc_heuristic=e["pc_heuristic"],
            sphere_radius_km=e["sphere_radius_km"],
            eci_mid_m=e["eci_mid_m"],
            primary_eci_m=e["primary_eci_m"],
            secondary_eci_m=e["secondary_eci_m"],
        )
        for e in raw
    ]
    return CatalogScreenResponse(sim_utc=sim.isoformat(), events=events)


@router.get("/")
async def list_conjunctions() -> dict[str, str]:
    _ = _LIB_SURFACE
    return {
        "detail": (
            "POST /conjunctions/catalog-screen (subset SGP4 sweep) · "
            "POST /conjunctions/pair-screen (TLE+SGP4) · "
            "POST /conjunctions/keplerian/pair-screen (mean elements)."
        )
    }


@router.get("/{conjunction_id}")
async def get_conjunction(conjunction_id: str) -> dict[str, str]:
    _ = _LIB_SURFACE
    return {"detail": f"Conjunction {conjunction_id} record retrieval not implemented."}


@router.post("/pair-screen", response_model=PairSphereScreenResponse)
async def pair_screen_sphere(body: PairSphereScreenRequest) -> PairSphereScreenResponse:
    """SGP4 both satellites; flag external entering ego's sphere; heuristic conjunction probability."""
    if body.start_utc.tzinfo is None:
        raise HTTPException(status_code=400, detail="start_utc must be timezone-aware.")

    try:
        r = screen_pair_sphere_sgp4(
            body.my_spacecraft.line1,
            body.my_spacecraft.line2,
            body.external_spacecraft.line1,
            body.external_spacecraft.line2,
            body.start_utc.astimezone(timezone.utc),
            sphere_radius_km=body.sphere_radius_km,
            step_s=body.step_s,
            search_max_orbits=body.search_max_orbits,
            followup_orbits=body.followup_orbits,
            weight_distance=body.weight_distance,
            weight_time=body.weight_time,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    first = r.first_entry_utc.astimezone(timezone.utc) if r.first_entry_utc else None

    return PairSphereScreenResponse(
        conjunction_occurred=r.conjunction_occurred,
        conjunction_probability_heuristic=r.probability_heuristic,
        closest_approach_km=r.closest_approach_km,
        first_entry_utc=first,
        my_orbital_period_s=r.my_orbital_period_s,
        time_points_inside_sphere=r.time_points_inside_sphere,
        total_time_points=r.total_time_points,
        time_spent_inside_s=r.time_spent_inside_s,
        integration_start_utc=r.integration_start_utc.astimezone(timezone.utc),
        integration_end_utc=r.integration_end_utc.astimezone(timezone.utc),
        step_s=r.step_s,
        sphere_radius_km=r.sphere_radius_km,
        weight_distance_applied=r.weight_distance,
        weight_time_applied=r.weight_time,
    )


@router.post("/keplerian/pair-screen", response_model=KeplerianPairKeepoutResponse)
async def keplerian_pair_screen_keepout(body: KeplerianPairKeepoutRequest) -> KeplerianPairKeepoutResponse:
    """Screen two Keplerian orbits for external entry into a sphere around the ego satellite."""
    if body.start_utc.tzinfo is None:
        raise HTTPException(status_code=400, detail="start_utc must be timezone-aware.")

    start = Epoch(instant=body.start_utc.astimezone(timezone.utc), scale=TimeScale.UTC)
    try:
        r: KeplerianPairKeepoutResult = screen_pair_keplerian_keepout(
            body.my_spacecraft,
            body.external_spacecraft,
            start,
            body.horizon_duration_s,
            body.keep_out_sphere_radius_km,
            step_s=body.step_s,
            weight_distance=body.weight_distance,
            weight_time=body.weight_time,
            use_j2=body.use_j2,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    first = r.first_conjunction_utc.astimezone(timezone.utc) if r.first_conjunction_utc else None

    return KeplerianPairKeepoutResponse(
        conjunction_occurred=r.conjunction_occurred,
        first_conjunction_utc=first,
        conjunction_score_normalized=r.conjunction_score_normalized,
        closest_approach_km=r.closest_approach_km,
        time_points_inside_sphere=r.time_points_inside_sphere,
        total_time_points=r.total_time_points,
        integration_start_utc=r.integration_start_utc.astimezone(timezone.utc),
        integration_end_utc=r.integration_end_utc.astimezone(timezone.utc),
        step_s=r.step_s,
        horizon_duration_s=r.horizon_s,
        keep_out_sphere_radius_km=r.keep_out_sphere_radius_km,
        weight_distance_applied=r.weight_distance_applied,
        weight_time_applied=r.weight_time_applied,
    )
