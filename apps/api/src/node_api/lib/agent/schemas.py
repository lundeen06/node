"""Anthropic Messages API tool definitions (name + description + input_schema)."""

from __future__ import annotations

AGENT_TOOLS: list[dict[str, object]] = [
    {
        "name": "get_operator_reference",
        "description": (
            "Return authoritative id lists: house-rule constellation keys, Space-Track ingest preset "
            "ids (e.g. starlink), SQLite catalog sat_ids, and mock fuel registry ids. Call this when the "
            "operator asks what constellations "
            "or presets exist, or before guessing constellation_id for get_house_rules."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_fleet_conjunctions",
        "description": (
            "List all active conjunction events in the forward window from the latest catalog-screen "
            "snapshot (every pair), without naming a satellite. Use for fleet-wide situational "
            "awareness; use get_active_conjunctions for one ego sat_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "horizon_hours": {
                    "type": "integer",
                    "description": "Look-ahead window in hours (default 36)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_active_conjunctions",
        "description": (
            "Retrieve active conjunctions (NEW or ACKNOWLEDGED) for a satellite within a "
            "time horizon from the latest catalog-screen SQLite snapshot. Returns TCA, miss distance, "
            "Pc, and status for each event."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sat_id": {
                    "type": "string",
                    "description": "Satellite ID (matches catalog sat_id; ego may be primary or secondary)",
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
            "Compute time from a reference epoch to persisted catalog-screen TCA in "
            "seconds and hours. Omit reference_utc to use server UTC now."
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
            "Return RIC delta-v for a persisted mitigation template. Catalog-screen conjunctions "
            "do not have templates yet — expect an error directing you to external CA sizing."
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
            "Compare screening Pc to the mitigation threshold; post-burn Pc is not modeled until "
            "maneuver templates exist."
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
            "Build a Lambert single-impulse avoidance plan from the catalog TLE and a persisted "
            "catalog-screen conjunction (sat_id must be the event primary). Returns maneuvers with "
            "epoch_utc, delta_v_mps (ECI m/s), frame, and validation entries for the UI."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "conjunction_id": {
                    "type": "string",
                    "description": "Conjunction ID from get_active_conjunctions / catalog screening",
                },
                "sat_id": {"type": "string", "description": "Satellite to maneuver"},
            },
            "required": ["conjunction_id", "sat_id"],
        },
    },
    {
        "name": "check_maneuver_feasibility",
        "description": (
            "Re-run the Lambert avoidance planner for the conjunction primary and report whether "
            "total Δv is within house-rules max_auto_delta_v_mps."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"conjunction_id": {"type": "string"}},
            "required": ["conjunction_id"],
        },
    },
]


def openai_chat_tools() -> list[dict[str, object]]:
    """Map ``AGENT_TOOLS`` to OpenAI Chat Completions ``tools`` format."""
    out: list[dict[str, object]] = []
    for t in AGENT_TOOLS:
        out.append(
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            },
        )
    return out


OPENAI_CHAT_TOOLS: list[dict[str, object]] = openai_chat_tools()
