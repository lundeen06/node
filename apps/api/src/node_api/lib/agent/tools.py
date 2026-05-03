"""Tool function implementations for the orbital operations agent.

Each function corresponds to one Anthropic tool schema in schemas.py.
Returns plain dicts (JSON-serializable) to be fed back to Claude as tool results.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from sqlalchemy import select

from node_api.db.models import ConjunctionEventRow, SpacecraftRow
from node_api.db.session import SessionLocal
from node_api.errors import InfeasibleProblemError
from node_api.lib.agent.mock_store import HOUSE_RULES, SATELLITES
from node_api.lib.agent.plan_validation import burn_epoch_future_validation_row
from node_api.lib.ingress.constellation_presets import list_preset_ids
from node_api.lib.mission.circular_altitude_transfer import (
    plan_lambert_two_burn_circular_altitude_change,
)
from node_api.lib.mission.collision_avoidance import plan_collision_avoidance as run_lambert_plan
from node_api.lib.mission.burn_utility_preview import preview_plan_utility_vs_catalog_tle
from node_api.lib.mission.ground_track_utility import orbit_dual_deviation_report, orbit_utility_breakdown
from node_api.lib.tle_physics import trajectory_states_sgp4
from node_api.services.spacecraft_catalog import resolve_spacecraft_row
from node_api.services.conjunction_store import (
    get_conjunction_by_id,
    list_active_conjunctions_for_sat,
    list_all_active_conjunctions,
)
from node_api.types.common import Matrix6x6, Vector3
from node_api.types.conjunction import Conjunction, ConjunctionSource, ConjunctionStatus, PcMethod
from node_api.types.constellation import HouseRules
from node_api.types.frames import Frame
from node_api.types.maneuver import ManeuverPlan
from node_api.types.satellite import DataQuality, SatelliteState
from node_api.types.state import Covariance6x6, StateVector
from node_api.types.time import Epoch, TimeScale


def evaluate_orbit_mission_value(
    sat_id: str,
    baseline_tle_line1: str | None = None,
    baseline_tle_line2: str | None = None,
    candidate_tle_line1: str | None = None,
    candidate_tle_line2: str | None = None,
    t0_utc: str | None = None,
    t1_utc: str | None = None,
    n_samples: int = 48,
    delta_v_used_mps: float | None = None,
    delta_v_budget_mps: float | None = None,
    length_scale_track_km: float = 25.0,
    length_scale_eci_km: float = 5.0,
    w_track: float = 1.0,
    w_eci: float = 1.0,
    w_fuel: float = 1.0,
) -> dict[str, Any]:
    """Parallel ground-track + ECI RMSE vs nominal TLE, utilities, and Δv-budget loss (catalog defaults)."""
    db = SessionLocal()
    try:
        srow = resolve_spacecraft_row(db, sat_id)
        if srow is None:
            return {
                "error": f"No catalog spacecraft matches {sat_id!r}.",
                "hint": "Call get_operator_reference for catalog_entries / sat_id list.",
            }
        if bool(baseline_tle_line1) ^ bool(baseline_tle_line2):
            return {"error": "Provide both baseline_tle_line1 and baseline_tle_line2, or neither."}
        if bool(candidate_tle_line1) ^ bool(candidate_tle_line2):
            return {"error": "Provide both candidate_tle_line1 and candidate_tle_line2, or neither."}
        b1 = baseline_tle_line1 or srow.tle_line1
        b2 = baseline_tle_line2 or srow.tle_line2
        c1 = candidate_tle_line1 or srow.tle_line1
        c2 = candidate_tle_line2 or srow.tle_line2
        now = datetime.now(UTC)
        t0 = _parse_utc(t0_utc) if t0_utc else now
        t1 = _parse_utc(t1_utc) if t1_utc else now + timedelta(hours=12)
        ns = max(2, min(int(n_samples), 200))
        rules = _house_rules_for_sat(srow.sat_id)
        dv_used = 0.0 if delta_v_used_mps is None else float(delta_v_used_mps)
        dv_budget = float(rules.max_auto_delta_v_mps) if delta_v_budget_mps is None else float(delta_v_budget_mps)
        dv_budget = max(dv_budget, 1e-6)
        same_tle = b1.strip() == c1.strip() and b2.strip() == c2.strip()
        dual = orbit_dual_deviation_report(b1, b2, c1, c2, t0, t1, n_samples=ns)
        util = orbit_utility_breakdown(
            b1,
            b2,
            c1,
            c2,
            t0,
            t1,
            delta_v_used_mps=dv_used,
            delta_v_budget_mps=dv_budget,
            n_samples=ns,
            length_scale_track_km=float(length_scale_track_km),
            length_scale_eci_km=float(length_scale_eci_km),
            w_track=float(w_track),
            w_eci=float(w_eci),
            w_fuel=float(w_fuel),
        )
        out: dict[str, Any] = {
            "sat_id": srow.sat_id,
            "norad_catalog_id": srow.norad_catalog_id,
            "t0_utc": t0.isoformat().replace("+00:00", "Z"),
            "t1_utc": t1.isoformat().replace("+00:00", "Z"),
            "n_samples": ns,
            "baseline_source": "argument" if (baseline_tle_line1 and baseline_tle_line2) else "catalog",
            "candidate_source": "argument" if (candidate_tle_line1 and candidate_tle_line2) else "catalog",
            "measures_two_tle_ephemeris_difference": not same_tle,
            "parallel_deviation": dual.model_dump(),
            "utility_and_loss": util.model_dump(),
            "note": (
                "parallel_deviation compares two TLEs propagated with SGP4 (same UTC lattice). "
                "Pass baseline_tle_line* for a frozen mission reference and candidate_tle_line* for a "
                "different mean element set (e.g. post-fit TLE)."
            ),
        }
        if same_tle:
            out["warning"] = (
                "Baseline and candidate are the same catalog TLE lines: RMSE and utility here are a sanity "
                "check (~0) and do **not** measure maneuver impact or post-burn vs ideal orbit. For Δv plan "
                "tradeoffs vs no-burn catalog, use **utility_preview** from plan_collision_avoidance or "
                "plan_orbit_altitude_change (already returned with the plan). For strict TLE-vs-TLE after a "
                "new element set exists, call this tool again with distinct candidate_tle_line*."
            )
        return out
    finally:
        db.close()


def plan_orbit_altitude_change(
    sat_id: str,
    target_circular_altitude_km: float,
    reference_utc: str | None = None,
) -> dict[str, Any]:
    """Lambert transfer leg + circularization to a target **circular** altitude (km above mean Earth sphere)."""
    db = SessionLocal()
    try:
        srow = resolve_spacecraft_row(db, sat_id)
        if srow is None:
            return {
                "error": f"No catalog spacecraft matches {sat_id!r}.",
                "hint": (
                    "Call get_operator_reference: use catalog_entries[].sat_id, or the same NORAD id "
                    "as norad_catalog_id, or a distinctive name substring (e.g. ISS (demo))."
                ),
            }
        when = _parse_utc(reference_utc) if reference_utc else datetime.now(UTC)
        plan_not_before = datetime.now(UTC)
        _, r_km, v_km_s = trajectory_states_sgp4(srow.tle_line1, srow.tle_line2, [when])[0]
        r1_m = np.asarray(r_km, dtype=np.float64) * 1000.0
        v1_mps = np.asarray(v_km_s, dtype=np.float64) * 1000.0
        dep_epoch = Epoch(instant=when, scale=TimeScale.UTC)
        try:
            plan = plan_lambert_two_burn_circular_altitude_change(
                r1_m,
                v1_mps,
                float(target_circular_altitude_km),
                dep_epoch,
                srow.sat_id,
            )
        except InfeasibleProblemError as exc:
            return {
                "error": str(exc),
                "hint": (
                    "Target must be a circular altitude in km above Earth mean radius; initial and target "
                    "radii must differ by enough for a Hohmann-like Lambert leg. Try a different altitude or "
                    "reference_utc."
                ),
            }
        rules = _house_rules_for_sat(srow.sat_id)
        return {
            "plan": _maneuver_plan_to_tool_dict(plan, not_before=plan_not_before),
            "utility_preview": _utility_preview_for_catalog_plan(srow, plan, rules),
            "note": (
                "Two ECI burns: Lambert arc to the antipodal point on the target circular orbit, then "
                "circularization. Coplanar with the current osculating plane from SGP4 at reference_utc "
                "(server UTC if omitted). utility_preview scores orbit / ground-track departure from the "
                "catalog SGP4 if you never burn vs post-maneuver two-body coast over one Kozai period."
            ),
        }
    finally:
        db.close()


def _parse_utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


def _utility_preview_for_catalog_plan(srow: SpacecraftRow, plan: ManeuverPlan, rules: HouseRules) -> dict[str, Any]:
    """Post-burn path vs catalog SGP4 if you never burn, over one Kozai period; Δv vs house-rules budget."""
    return preview_plan_utility_vs_catalog_tle(
        srow.tle_line1,
        srow.tle_line2,
        list(plan.maneuvers),
        n_samples=48,
        delta_v_budget_mps=float(rules.max_auto_delta_v_mps),
        delta_v_used_mps=float(plan.total_delta_v_mps),
    )


def get_operator_reference() -> dict[str, Any]:
    """Static + DB ids so the model does not hallucinate constellation or preset namespaces."""
    db = SessionLocal()
    try:
        catalog_ids = list(
            db.scalars(select(SpacecraftRow.sat_id).order_by(SpacecraftRow.sat_id).limit(500)),
        )
        catalog_rows = list(
            db.scalars(select(SpacecraftRow).order_by(SpacecraftRow.sat_id).limit(300)),
        )
        catalog_entries = [
            {"sat_id": r.sat_id, "norad_catalog_id": r.norad_catalog_id, "name": r.name}
            for r in catalog_rows
        ]
    finally:
        db.close()
    return {
        "house_rule_constellation_ids": sorted(HOUSE_RULES.keys()),
        "space_track_ingest_preset_ids": list_preset_ids(),
        "catalog_satellite_ids": catalog_ids,
        "catalog_entries": catalog_entries,
        "mock_satellite_registry_ids": sorted(SATELLITES.keys()),
        "notes": [
            "House rules (Pc threshold, max auto-dV) use house_rule_constellation_ids — in this build "
            "that is mainly EO-CONSTELLATION for mock fuel/state.",
            "space_track_ingest_preset_ids are lowercase keys for importing GP data (e.g. starlink); "
            "they are not the same strings as house_rule_constellation_ids.",
            "Orbit tools resolve catalog rows by sat_id, NORAD catalog id (digits), or name substring — "
            "prefer catalog_entries for exact sat_id when calling plan_orbit_altitude_change.",
        ],
    }


def get_fleet_conjunctions(horizon_hours: int = 36) -> dict[str, Any]:
    """All active events in the latest catalog-screen snapshot (any satellite)."""
    db = SessionLocal()
    try:
        results = list_all_active_conjunctions(db, horizon_hours=horizon_hours)
    finally:
        db.close()
    return {
        "horizon_hours": horizon_hours,
        "count": len(results),
        "conjunctions": results,
        "source_note": "Union of events from the latest POST /conjunctions/catalog-screen snapshot.",
    }


def get_active_conjunctions(sat_id: str, horizon_hours: int = 36) -> dict[str, Any]:
    db = SessionLocal()
    try:
        results = list_active_conjunctions_for_sat(
            db, sat_id=sat_id, horizon_hours=horizon_hours
        )
    finally:
        db.close()
    return {
        "sat_id": sat_id,
        "horizon_hours": horizon_hours,
        "count": len(results),
        "conjunctions": results,
        "source_note": "Events from the latest POST /conjunctions/catalog-screen snapshot (SQLite).",
    }


def get_satellite_state(sat_id: str) -> dict[str, Any]:
    sat = SATELLITES.get(sat_id)
    if sat is None:
        return {"error": f"Unknown satellite: {sat_id}"}
    return sat


def get_house_rules(constellation_id: str) -> dict[str, Any]:
    rules = HOUSE_RULES.get(constellation_id)
    if rules is None:
        return {"error": f"Unknown constellation: {constellation_id}"}
    return rules


def compute_time_to_tca(conjunction_id: str, reference_utc: str | None = None) -> dict[str, Any]:
    """Seconds from a reference epoch to persisted catalog-screen TCA."""
    db = SessionLocal()
    try:
        row = get_conjunction_by_id(db, conjunction_id)
    finally:
        db.close()
    if row is None:
        return {"error": f"Unknown conjunction: {conjunction_id} (run catalog-screen first)."}
    c = {
        "primary_id": row.primary_id,
        "tca_utc": row.tca_utc.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }
    tca = _parse_utc(c["tca_utc"])
    if reference_utc:
        t0 = _parse_utc(reference_utc)
        ref_label = reference_utc
    else:
        t0 = datetime.now(UTC)
        ref_label = t0.isoformat().replace("+00:00", "Z") + " (server UTC now)"
    dt_s = max(0.0, (tca - t0).total_seconds())
    return {
        "conjunction_id": conjunction_id,
        "tca_utc": c["tca_utc"],
        "reference_utc": ref_label,
        "time_to_tca_s": dt_s,
        "time_to_tca_h": dt_s / 3600.0,
    }


def compute_required_delta_v(conjunction_id: str) -> dict[str, Any]:
    """RIC Δv for a stored mitigation template (not generated for catalog-screen events yet)."""
    _ = conjunction_id
    return {
        "error": (
            "No maneuver template is stored for catalog-screen conjunctions. "
            "Size burns with your operational CA workflow or external solver; "
            "this tool will attach once mitigation plans are persisted."
        ),
    }


def compute_fuel_from_tsiolkovsky(
    sat_id: str,
    delta_v_mps: float,
    specific_impulse_s: float = 220.0,
    g0_mps2: float = 9.80665,
) -> dict[str, Any]:
    """Propellant mass via Tsiolkovsky (ideal rocket); toy wet mass for order-of-magnitude demos."""
    sat = SATELLITES.get(sat_id)
    if sat is None:
        return {"error": f"Unknown satellite: {sat_id}"}
    ve = specific_impulse_s * g0_mps2
    if ve <= 0:
        return {"error": "Invalid exhaust velocity (Isp × g0)."}
    # Toy wet mass for demo-scale propellant estimates.
    m0_effective_kg = 80.0
    fraction = 1.0 - math.exp(-delta_v_mps / ve)
    propellant_kg = m0_effective_kg * fraction
    remaining_kg = float(sat["fuel_kg"]) - propellant_kg
    return {
        "sat_id": sat_id,
        "delta_v_mps": delta_v_mps,
        "specific_impulse_s": specific_impulse_s,
        "effective_exhaust_velocity_mps": ve,
        "effective_initial_mass_kg": m0_effective_kg,
        "propellant_consumed_kg": propellant_kg,
        "fuel_remaining_after_kg": remaining_kg,
    }


def estimate_post_maneuver_pc(conjunction_id: str) -> dict[str, Any]:
    """Screening Pc vs house rules; post-burn Pc needs a propagated maneuver (not stored here)."""
    db = SessionLocal()
    try:
        row = get_conjunction_by_id(db, conjunction_id)
    finally:
        db.close()
    if row is None:
        return {"error": f"Unknown conjunction: {conjunction_id} (run catalog-screen first)."}
    sat = SATELLITES.get(row.primary_id)
    default_thr = 1e-4
    if sat is None:
        thr = default_thr
        thr_note = (
            f"No mock satellite registry entry for primary `{row.primary_id}`; "
            f"using default mitigation Pc threshold {thr:g}."
        )
    else:
        const_id = sat["constellation_id"]
        rules = HOUSE_RULES.get(const_id)
        if rules is None:
            thr = default_thr
            thr_note = f"Unknown constellation `{const_id}`; using default threshold {thr:g}."
        else:
            thr = float(rules["pc_mitigation_threshold"])
            thr_note = f"Threshold from house rules for `{const_id}`."
    pc_prior = float(row.pc)
    return {
        "conjunction_id": conjunction_id,
        "pc_prior": pc_prior,
        "pc_method": row.pc_method,
        "data_source": row.source,
        "mitigation_pc_threshold": thr,
        "threshold_note": thr_note,
        "note": (
            "Post-maneuver Pc is not computed for catalog-screen events without a maneuver template. "
            "Compare screening Pc to threshold; use UI-provided TCA when present."
        ),
        "below_mitigation_threshold": pc_prior < thr,
    }


def _pc_method_from_db(s: str) -> PcMethod:
    try:
        return PcMethod(s)
    except ValueError:
        return PcMethod.SCREEN_HEURISTIC


def _conjunction_source_from_db(s: str) -> ConjunctionSource:
    try:
        return ConjunctionSource(s)
    except ValueError:
        return ConjunctionSource.INTERNAL_SCREENING


def _conjunction_status_from_db(s: str) -> ConjunctionStatus:
    try:
        return ConjunctionStatus(s)
    except ValueError:
        return ConjunctionStatus.NEW


def _conjunction_from_row(row: ConjunctionEventRow) -> Conjunction:
    tca = Epoch(instant=row.tca_utc.astimezone(UTC), scale=TimeScale.UTC)
    created = Epoch(instant=row.created_at.astimezone(UTC), scale=TimeScale.UTC)
    return Conjunction(
        id=row.id,
        primary_id=row.primary_id,
        secondary_id=row.secondary_id,
        tca=tca,
        miss_distance_km=float(row.miss_distance_km),
        relative_velocity_km_s=max(1e-6, float(row.relative_velocity_km_s or 0.0)),
        pc=float(row.pc),
        pc_method=_pc_method_from_db(row.pc_method),
        source=_conjunction_source_from_db(row.source),
        created_at=created,
        status=_conjunction_status_from_db(row.status),
    )


def _house_rules_for_sat(sat_id: str) -> HouseRules:
    meta = SATELLITES.get(sat_id)
    if meta:
        cid = str(meta["constellation_id"])
        d = HOUSE_RULES.get(cid)
        if d is not None:
            return HouseRules(**d)
    return HouseRules(**HOUSE_RULES["CATALOG-DEFAULT"])


def _satellite_state_from_row(srow: SpacecraftRow, when: datetime) -> SatelliteState:
    when_utc = when.astimezone(UTC)
    _, r_km, v_km_s = trajectory_states_sgp4(srow.tle_line1, srow.tle_line2, [when_utc])[0]
    epoch = Epoch(instant=when_utc, scale=TimeScale.UTC)
    st = StateVector(
        position_km=Vector3(data=np.asarray(r_km, dtype=np.float64)),
        velocity_km_s=Vector3(data=np.asarray(v_km_s, dtype=np.float64)),
        epoch=epoch,
        frame=Frame.ECI_J2000,
    )
    diag = np.diag([1.0, 1.0, 1.0, 1e-6, 1e-6, 1e-6]).astype(np.float64)
    cov = Covariance6x6(matrix=Matrix6x6(data=diag), epoch=epoch, frame=Frame.ECI_J2000)
    meta = SATELLITES.get(srow.sat_id)
    fuel = float(meta["fuel_kg"]) if meta else 100.0
    return SatelliteState(
        sat_id=srow.sat_id,
        state_vector=st,
        covariance=cov,
        fuel_kg=fuel,
        last_updated=epoch,
        data_quality=DataQuality.NOMINAL,
    )


def _state_vector_to_tool_dict(st: StateVector) -> dict[str, Any]:
    p = np.asarray(st.position_km.data, dtype=np.float64).reshape(3)
    v = np.asarray(st.velocity_km_s.data, dtype=np.float64).reshape(3)
    return {
        "epoch_utc": st.epoch.as_utc_datetime().isoformat().replace("+00:00", "Z"),
        "frame": st.frame.value,
        "position_km": {"x": float(p[0]), "y": float(p[1]), "z": float(p[2])},
        "velocity_km_s": {"x": float(v[0]), "y": float(v[1]), "z": float(v[2])},
    }


def _maneuver_plan_to_tool_dict(plan: ManeuverPlan, *, not_before: datetime | None = None) -> dict[str, Any]:
    ref = (not_before or datetime.now(UTC)).astimezone(UTC)
    maneuvers: list[dict[str, Any]] = []
    for m in plan.maneuvers:
        dv = np.asarray(m.delta_v.data, dtype=np.float64).reshape(3)
        maneuvers.append(
            {
                "epoch_utc": m.epoch.as_utc_datetime()
                .isoformat()
                .replace("+00:00", "Z"),
                "delta_v_mps": {"x": float(dv[0]), "y": float(dv[1]), "z": float(dv[2])},
                "frame": m.frame.value,
                "duration_s": m.duration_s,
            },
        )
    validation = [
        {"passed": v.passed, "check_id": v.check_id, "message": v.message}
        for v in plan.validation_results
    ]
    validation.append(burn_epoch_future_validation_row(maneuvers, ref))
    return {
        "plan_id": str(uuid.uuid4()),
        "sat_id": plan.sat_id,
        "maneuvers": maneuvers,
        "total_delta_v_mps": plan.total_delta_v_mps,
        "objective": plan.objective,
        "generated_by": plan.generated_by.value,
        "validation": validation,
        "predicted_post_state": _state_vector_to_tool_dict(plan.predicted_post_state),
        "time_of_flight_s": plan.time_of_flight_s,
    }


def plan_collision_avoidance(conjunction_id: str, sat_id: str) -> dict[str, Any]:
    """Lambert-backed avoidance from catalog TLE + SQLite conjunction row (primary must match sat_id)."""
    db = SessionLocal()
    try:
        row = get_conjunction_by_id(db, conjunction_id)
        if row is None:
            return {"error": "Unknown conjunction_id; run catalog-screen first."}
        primary_row = resolve_spacecraft_row(db, row.primary_id)
        if primary_row is None:
            return {"error": f"No catalog spacecraft matches conjunction primary {row.primary_id!r}."}
        srow = resolve_spacecraft_row(db, sat_id)
        if srow is None:
            return {
                "error": f"No catalog spacecraft matches {sat_id!r}.",
                "hint": "Use conjunction primary sat_id or NORAD/name per get_operator_reference.catalog_entries.",
            }
        if srow.sat_id != primary_row.sat_id:
            return {
                "error": (
                    f"sat_id must identify the same catalog object as the primary "
                    f"({primary_row.sat_id!r}, NORAD {primary_row.norad_catalog_id}); "
                    f"resolved to {srow.sat_id!r}."
                ),
            }
        when = datetime.now(UTC)
        plan_not_before = when
        ego = _satellite_state_from_row(srow, when)
        cj = _conjunction_from_row(row)
        rules = _house_rules_for_sat(srow.sat_id)
        try:
            plan = run_lambert_plan(ego, cj, rules, tle_line1=srow.tle_line1, tle_line2=srow.tle_line2)
        except InfeasibleProblemError as exc:
            return {
                "error": str(exc),
                "hint": (
                    "TCA may be too soon for a pre-TCA Lambert leg, or max_auto_delta_v_mps may be too low "
                    "for the required separation."
                ),
            }
        return {
            "plan": _maneuver_plan_to_tool_dict(plan, not_before=plan_not_before),
            "utility_preview": _utility_preview_for_catalog_plan(srow, plan, rules),
            "note": (
                "Lambert single-impulse avoidance (multi-lead timing search): departure state is SGP4 at the "
                "burn epoch from the catalog TLE (not stale PV with only the epoch changed). "
                "utility_preview: post-maneuver path vs ideal no-burn SGP4 (catalog TLE until a mission baseline "
                "exists), samples from first_burn+1s over one Kozai period; summed squared losses, calibration, "
                "utility vs max_auto_delta_v_mps."
            ),
        }
    finally:
        db.close()


def check_maneuver_feasibility(conjunction_id: str) -> dict[str, Any]:
    """Re-run Lambert planner for the conjunction primary vs house rules (no separate stored plan)."""
    db = SessionLocal()
    try:
        row = get_conjunction_by_id(db, conjunction_id)
        if row is None:
            return {"error": "Unknown conjunction_id; run catalog-screen first."}
        sat_id = row.primary_id
        srow = resolve_spacecraft_row(db, sat_id)
        if srow is None:
            return {"error": f"No catalog spacecraft matches primary {sat_id!r}."}
        when = datetime.now(UTC)
        ego = _satellite_state_from_row(srow, when)
        cj = _conjunction_from_row(row)
        rules = _house_rules_for_sat(sat_id)
        try:
            plan = run_lambert_plan(ego, cj, rules, tle_line1=srow.tle_line1, tle_line2=srow.tle_line2)
        except InfeasibleProblemError as exc:
            return {
                "feasible": False,
                "conjunction_id": conjunction_id,
                "primary_id": sat_id,
                "reason": str(exc),
            }
        feasible = plan.total_delta_v_mps <= rules.max_auto_delta_v_mps + 1e-9
        return {
            "feasible": feasible,
            "conjunction_id": conjunction_id,
            "primary_id": sat_id,
            "total_delta_v_mps": plan.total_delta_v_mps,
            "max_auto_delta_v_mps": rules.max_auto_delta_v_mps,
            "maneuver_count": len(plan.maneuvers),
            "validation_all_passed": all(v.passed for v in plan.validation_results),
        }
    finally:
        db.close()


TOOL_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    "get_operator_reference": get_operator_reference,
    "evaluate_orbit_mission_value": evaluate_orbit_mission_value,
    "get_fleet_conjunctions": get_fleet_conjunctions,
    "get_active_conjunctions": get_active_conjunctions,
    "get_satellite_state": get_satellite_state,
    "get_house_rules": get_house_rules,
    "compute_time_to_tca": compute_time_to_tca,
    "compute_required_delta_v": compute_required_delta_v,
    "compute_fuel_from_tsiolkovsky": compute_fuel_from_tsiolkovsky,
    "estimate_post_maneuver_pc": estimate_post_maneuver_pc,
    "plan_collision_avoidance": plan_collision_avoidance,
    "check_maneuver_feasibility": check_maneuver_feasibility,
    "plan_orbit_altitude_change": plan_orbit_altitude_change,
}
