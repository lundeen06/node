"""Anthropic Messages API tool definitions (name + description + input_schema)."""

from __future__ import annotations

AGENT_TOOLS: list[dict[str, object]] = [
    {
        "name": "get_active_conjunctions",
        "description": (
            "Retrieve active conjunctions (NEW or ACKNOWLEDGED) for a satellite within a "
            "time horizon. Returns TCA, miss distance, Pc, and status for each event."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sat_id": {
                    "type": "string",
                    "description": "Satellite ID (e.g. 'EO-12')",
                },
                "horizon_hours": {
                    "type": "integer",
                    "description": "Look-ahead window in hours (default 36)",
                },
            },
            "required": ["sat_id"],
        },
    },
    {
        "name": "get_satellite_state",
        "description": (
            "Get the current best-estimate state for a satellite: fuel remaining, "
            "data quality, and last update time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"sat_id": {"type": "string"}},
            "required": ["sat_id"],
        },
    },
    {
        "name": "get_house_rules",
        "description": (
            "Get operational house rules for a constellation: Pc mitigation threshold and "
            "max auto-execute delta-v limit."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"constellation_id": {"type": "string"}},
            "required": ["constellation_id"],
        },
    },
    {
        "name": "compute_time_to_tca",
        "description": (
            "Compute time from a reference epoch to conjunction closest approach (TCA) in "
            "seconds and hours. Omit reference_utc to use the primary's last state update as 'now'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "conjunction_id": {"type": "string"},
                "reference_utc": {
                    "type": "string",
                    "description": "Optional ISO-8601 UTC instant (e.g. ends with Z)",
                },
            },
            "required": ["conjunction_id"],
        },
    },
    {
        "name": "compute_required_delta_v",
        "description": (
            "Return the RIC delta-v vector and magnitudes for the mitigation template tied to "
            "this conjunction (numeric solver output for audit)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"conjunction_id": {"type": "string"}},
            "required": ["conjunction_id"],
        },
    },
    {
        "name": "compute_fuel_from_tsiolkovsky",
        "description": (
            "Estimate propellant consumed for a finite Δv using the Tsiolkovsky rocket equation "
            "(ideal, fixed Isp). Returns consumed mass and projected remaining fuel."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sat_id": {"type": "string"},
                "delta_v_mps": {"type": "number", "description": "Scalar Δv magnitude in m/s"},
                "specific_impulse_s": {
                    "type": "number",
                    "description": "Specific impulse in seconds (default 220)",
                },
            },
            "required": ["sat_id", "delta_v_mps"],
        },
    },
    {
        "name": "estimate_post_maneuver_pc",
        "description": (
            "Estimate conjunction Pc after the template maneuver (mock propagation); compare to "
            "the constellation mitigation threshold."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"conjunction_id": {"type": "string"}},
            "required": ["conjunction_id"],
        },
    },
    {
        "name": "plan_collision_avoidance",
        "description": (
            "Assemble the full maneuver plan record (burn epoch, RIC Δv, objective) after numeric "
            "solver steps. Stores the plan for the UI."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "conjunction_id": {
                    "type": "string",
                    "description": "ID of the conjunction to mitigate (e.g. 'CJX-2041')",
                },
                "sat_id": {"type": "string", "description": "Satellite to maneuver"},
            },
            "required": ["conjunction_id", "sat_id"],
        },
    },
    {
        "name": "check_maneuver_feasibility",
        "description": (
            "Validate the maneuver plan: induced conjunctions, fuel compliance, and keep-out "
            "zone compliance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"conjunction_id": {"type": "string"}},
            "required": ["conjunction_id"],
        },
    },
]
