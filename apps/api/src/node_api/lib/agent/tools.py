"""Tool function implementations for the orbital operations agent.

Each function corresponds to one Anthropic tool schema in schemas.py.
Returns plain dicts (JSON-serializable) to be fed back to Claude as tool results.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from node_api.lib.agent.mock_store import CONJUNCTIONS, HOUSE_RULES, PLANS, SATELLITES


def _parse_utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


def get_active_conjunctions(sat_id: str, horizon_hours: int = 36) -> dict[str, Any]:
    results = [
        c
        for c in CONJUNCTIONS.values()
        if c["primary_id"] == sat_id and c["status"] in ("NEW", "ACKNOWLEDGED")
    ]
    return {
        "sat_id": sat_id,
        "horizon_hours": horizon_hours,
        "count": len(results),
        "conjunctions": results,
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
    """Seconds from a reference epoch to conjunction TCA (mock ephemeris clock)."""
    c = CONJUNCTIONS.get(conjunction_id)
    if c is None:
        return {"error": f"Unknown conjunction: {conjunction_id}"}
    tca = _parse_utc(c["tca_utc"])
    if reference_utc:
        t0 = _parse_utc(reference_utc)
        ref_label = reference_utc
    else:
        sat = SATELLITES.get(c["primary_id"])
        if sat is None:
            t0 = datetime(2026, 5, 2, 14, 20, 0, tzinfo=UTC)
            ref_label = "2026-05-02T14:20:00Z (default ops clock)"
        else:
            ref_label = sat["last_updated_utc"]
            t0 = _parse_utc(ref_label)
    dt_s = max(0.0, (tca - t0).total_seconds())
    return {
        "conjunction_id": conjunction_id,
        "tca_utc": c["tca_utc"],
        "reference_utc": ref_label,
        "time_to_tca_s": dt_s,
        "time_to_tca_h": dt_s / 3600.0,
    }


def compute_required_delta_v(conjunction_id: str) -> dict[str, Any]:
    """RIC Δv vector and magnitude for the stored mitigation template (numeric audit step)."""
    plan = PLANS.get(conjunction_id)
    if plan is None:
        return {"error": f"No maneuver template for conjunction: {conjunction_id}"}
    dv = plan["maneuvers"][0]["delta_v_mps"]
    x, y, z = float(dv["x"]), float(dv["y"]), float(dv["z"])
    mag = math.sqrt(x * x + y * y + z * z)
    return {
        "conjunction_id": conjunction_id,
        "total_delta_v_mps": float(plan["total_delta_v_mps"]),
        "delta_v_ric_mps": {"x": x, "y": y, "z": z},
        "delta_v_magnitude_mps": mag,
    }


def compute_fuel_from_tsiolkovsky(
    sat_id: str,
    delta_v_mps: float,
    specific_impulse_s: float = 220.0,
    g0_mps2: float = 9.80665,
) -> dict[str, Any]:
    """Propellant mass via Tsiolkovsky (ideal rocket); effective wet mass calibrated to mock plan."""
    sat = SATELLITES.get(sat_id)
    if sat is None:
        return {"error": f"Unknown satellite: {sat_id}"}
    ve = specific_impulse_s * g0_mps2
    if ve <= 0:
        return {"error": "Invalid exhaust velocity (Isp × g0)."}
    # Toy wet mass so Δv ≈ 0.054 m/s ⇒ ≈ 0.002 kg consumed (matches validation copy in PLANS).
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
    """Mock post-burn Pc after executing the template maneuver (for threshold audit)."""
    c = CONJUNCTIONS.get(conjunction_id)
    if c is None:
        return {"error": f"Unknown conjunction: {conjunction_id}"}
    primary = c["primary_id"]
    sat = SATELLITES.get(primary)
    if sat is None:
        return {"error": f"Unknown primary satellite: {primary}"}
    const_id = sat["constellation_id"]
    rules = HOUSE_RULES.get(const_id)
    if rules is None:
        return {"error": f"Unknown constellation: {const_id}"}
    pc_prior = float(c["pc"])
    pc_post = 4.1e-5
    thr = float(rules["pc_mitigation_threshold"])
    return {
        "conjunction_id": conjunction_id,
        "pc_prior": pc_prior,
        "pc_post_estimate": pc_post,
        "mitigation_pc_threshold": thr,
        "below_mitigation_threshold": pc_post < thr,
    }


def plan_collision_avoidance(conjunction_id: str, sat_id: str) -> dict[str, Any]:
    plan = PLANS.get(conjunction_id)
    if plan is None:
        return {"error": f"No pre-computed plan for conjunction: {conjunction_id}"}
    if plan["sat_id"] != sat_id:
        return {"error": f"Plan for {conjunction_id} is for {plan['sat_id']}, not {sat_id}"}
    return {"status": "plan_generated", "plan": plan}


def check_maneuver_feasibility(conjunction_id: str) -> dict[str, Any]:
    plan = PLANS.get(conjunction_id)
    if plan is None:
        return {"error": f"No plan found for conjunction: {conjunction_id}"}
    all_passed = all(v["passed"] for v in plan["validation"])
    return {
        "conjunction_id": conjunction_id,
        "validation": plan["validation"],
        "all_passed": all_passed,
    }


TOOL_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    "get_active_conjunctions": get_active_conjunctions,
    "get_satellite_state": get_satellite_state,
    "get_house_rules": get_house_rules,
    "compute_time_to_tca": compute_time_to_tca,
    "compute_required_delta_v": compute_required_delta_v,
    "compute_fuel_from_tsiolkovsky": compute_fuel_from_tsiolkovsky,
    "estimate_post_maneuver_pc": estimate_post_maneuver_pc,
    "plan_collision_avoidance": plan_collision_avoidance,
    "check_maneuver_feasibility": check_maneuver_feasibility,
}
