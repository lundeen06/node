"""Planner HTTP surface: thin wrappers around orbit / mission solvers (physics-backed)."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from node_api.errors import InfeasibleProblemError
from node_api.lib.solvers.lambert import _lambert_vallado
from node_api.physics_runtime import ensure_physics_importable

ensure_physics_importable()
from physics.propulsion.util_dyn import mu_E as MU_EARTH_M3_S2  # noqa: E402

router = APIRouter()


class LambertChordRequest(BaseModel):
    """Two-body Lambert between position chords (SI). Same stack as ``node_api.lib.solvers.lambert``."""

    r0_m: tuple[float, float, float]
    r_m: tuple[float, float, float]
    tof_s: float = Field(..., gt=0)
    mu_m3_s2: float | None = Field(default=None, gt=0, description="Gravitational parameter; default Earth μ.")
    prograde: bool = True


class LambertChordResponse(BaseModel):
    v0_mps: list[float]
    v1_mps: list[float]
    mu_m3_s2: float


@router.post("/lambert/chord", response_model=LambertChordResponse)
def post_lambert_chord(body: LambertChordRequest) -> LambertChordResponse:
    mu = body.mu_m3_s2 if body.mu_m3_s2 is not None else float(MU_EARTH_M3_S2)
    r0 = np.asarray(body.r0_m, dtype=np.float64)
    r = np.asarray(body.r_m, dtype=np.float64)
    try:
        v0, v1 = _lambert_vallado(r0, r, body.tof_s, mu, prograde=body.prograde)
    except InfeasibleProblemError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return LambertChordResponse(v0_mps=v0.tolist(), v1_mps=v1.tolist(), mu_m3_s2=mu)
