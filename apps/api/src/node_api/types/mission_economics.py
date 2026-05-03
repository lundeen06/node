"""Per-asset Δv budgets and ground-track–based orbit value (loss / utility)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SatelliteDeltaVBudget(BaseModel):
    """Total propellant envelope for planning (annual, campaign, or remaining tank)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sat_id: str
    total_budget_mps: float = Field(..., ge=0, description="Scalar Δv budget, m/s.")
    label: str = Field(default="", description="Optional ops label, e.g. campaign or fiscal year.")


class GroundTrackDeviationReport(BaseModel):
    """How far subsatellite tracks diverge between a nominal TLE and a candidate TLE."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rmse_km: float = Field(..., ge=0, description="Root-mean-square great-circle separation, km.")
    mean_abs_km: float = Field(..., ge=0)
    max_km: float = Field(..., ge=0)
    mse_km2: float = Field(..., ge=0, description="Mean squared separation; loss often uses this directly.")
    n_samples: int = Field(..., ge=1)


class EciPositionDeviationReport(BaseModel):
    """‖r_nom − r_cand‖ in SGP4 TEME at common UTC samples (parallel to ground-track loss)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rmse_km: float = Field(..., ge=0, description="Root-mean-square 3D position separation, km.")
    mean_abs_km: float = Field(..., ge=0)
    max_km: float = Field(..., ge=0)
    mse_km2: float = Field(..., ge=0)
    n_samples: int = Field(..., ge=1)


class OrbitDeviationPairReport(BaseModel):
    """Ground footprint vs inertial geometry, same time lattice."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ground_track: GroundTrackDeviationReport
    eci_position: EciPositionDeviationReport


class OrbitUtilityBreakdown(BaseModel):
    """Scalar utility plus optional decomposition for planners / optimizers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ground_track_rmse_km: float = Field(..., ge=0)
    eci_position_rmse_km: float = Field(..., ge=0)
    utility_ground_track_unitless: float = Field(..., ge=0, le=1)
    utility_eci_position_unitless: float = Field(..., ge=0, le=1)
    utility_unitless: float = Field(
        ...,
        ge=0,
        le=1,
        description="Product of ground-track and ECI utilities (both 1 on the nominal orbit).",
    )
    track_opportunity_cost: float = Field(
        ...,
        ge=0,
        description="Ground track: −log(utility_ground_track); arbitrary units, linear in RMSE for exp kernel.",
    )
    eci_opportunity_cost: float = Field(
        ...,
        ge=0,
        description="ECI position tube: −log(utility_eci).",
    )
    delta_v_used_mps: float = Field(..., ge=0)
    delta_v_budget_mps: float = Field(..., ge=0)
    fuel_overrun_mps: float = Field(
        ...,
        ge=0,
        description="max(0, used − budget); zero when inside the Δv envelope.",
    )
    combined_loss: float = Field(
        ...,
        ge=0,
        description="w_track·track_opportunity_cost + w_eci·eci_opportunity_cost + normalized fuel overrun².",
    )
