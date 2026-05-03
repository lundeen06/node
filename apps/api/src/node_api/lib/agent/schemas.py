"""Function-calling tool definitions for the OpenAI Chat Completions API.

Each entry in ``_AGENT_TOOL_SPECS`` uses ``input_schema``. :data:`OPENAI_CHAT_TOOLS` is the
wire format (``type: "function"`` and ``parameters``).
"""

from __future__ import annotations

_AGENT_TOOL_SPECS: list[dict[str, object]] = [
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
            "Best-estimate state for a satellite. Tries the mock fuel registry first; if absent, "
            "falls back to the SQLite catalog row and returns SGP4 ECI position/velocity at server UTC, "
            "an inferred constellation_id (Starlink/Kuiper/Planet/Galileo/GPS/BeiDou or CATALOG-DEFAULT), "
            "and a 100 kg fuel placeholder so downstream tools (Tsiolkovsky, avoidance) can still run. "
            "Resolves by sat_id, NORAD digits, or distinctive name substring."
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
            "Operational house rules for a constellation: Pc mitigation threshold and max auto-execute "
            "delta-v limit. Unknown constellation_id returns CATALOG-DEFAULT with a note (never a hard "
            "error) — quote the note in your reply when you fall back."
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
            "Build an impulsive avoidance plan from the catalog TLE and a persisted catalog-screen "
            "conjunction (sat_id must be the event primary). Primary solver: Lambert chord to an out-of-plane "
            "offset at TCA under house-rule ‖Δv‖; extended burn-lead search up to ~24 h pre-TCA. If Lambert fails "
            "numerically or is Δv-bound, the server falls back to a cross-track impulse grid "
            "(``plan.objective`` contains ``cross_track_fallback`` when that path was used). Same wire format: maneuver epochs, delta_v_mps "
            "(ECI m/s). Always returns utility_preview (utility_unitless < 1 = mission degradation vs catalog "
            "no-burn baseline; cite RMSE, verdicts, combined_loss)."
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
            "Re-run the avoidance planner for the conjunction primary (Lambert primacy plus cross-track fallback) "
            "and report whether total Δv respects max_auto_delta_v_mps plus validation summary hints."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"conjunction_id": {"type": "string"}},
            "required": ["conjunction_id"],
        },
    },
    {
        "name": "evaluate_orbit_mission_value",
        "description": (
            "Compare **two TLEs** with SGP4 on the same UTC grid: ground-track RMSE (km) and ECI RMSE (km), "
            "utilities, combined_loss vs Δv budget. **Do not** use this with default catalog-only lines to "
            "answer \"utility after a maneuver\" — identical TLEs ⇒ ~0 RMSE (sanity only); response includes "
            "warning + measures_two_tle_ephemeris_difference=false. Post-burn vs ideal/no-burn catalog is "
            "**utility_preview** on plan_collision_avoidance / plan_orbit_altitude_change. Pass distinct "
            "baseline_tle_line* / candidate_tle_line* for refit or mission-freeze vs candidate ephemeris."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sat_id": {"type": "string", "description": "Catalog sat_id (see get_operator_reference)"},
                "baseline_tle_line1": {"type": "string", "description": "Optional NORAD line 1; with line 2 freezes reference"},
                "baseline_tle_line2": {"type": "string"},
                "candidate_tle_line1": {"type": "string", "description": "Optional line 1 for perturbed / post-burn mean state"},
                "candidate_tle_line2": {"type": "string"},
                "t0_utc": {"type": "string", "description": "ISO-8601 UTC window start (optional)"},
                "t1_utc": {"type": "string", "description": "ISO-8601 UTC window end (optional)"},
                "n_samples": {
                    "type": "integer",
                    "description": "Time samples in [t0,t1], clamped 2–200 (default 48)",
                },
                "delta_v_used_mps": {"type": "number", "description": "Propellant already spent this campaign (default 0)"},
                "delta_v_budget_mps": {
                    "type": "number",
                    "description": "Scalar budget m/s (default: constellation max_auto_delta_v_mps)",
                },
                "length_scale_track_km": {"type": "number", "description": "Ground-track exp kernel L, km (default 25)"},
                "length_scale_eci_km": {"type": "number", "description": "ECI tube exp kernel L, km (default 5)"},
                "w_track": {"type": "number", "description": "Weight on ground-track −log utility (default 1)"},
                "w_eci": {"type": "number", "description": "Weight on ECI −log utility (default 1)"},
                "w_fuel": {"type": "number", "description": "Weight on normalized fuel overrun² (default 1)"},
            },
            "required": ["sat_id"],
        },
    },
    {
        "name": "plan_orbit_altitude_change",
        "description": (
            "Plan a **two-burn** coplanar transfer to a **circular** target orbit using a **Lambert** "
            "leg (half-period transfer ellipse) plus a circularization burn. Uses the catalog TLE and "
            "SGP4 state at ``reference_utc`` (or server UTC now). ``target_circular_altitude_km`` is "
            "altitude above the mean Earth sphere (same R_E as physics util_dyn). Example: operator says "
            "raise orbit to 650 km → pass target_circular_altitude_km=650 and the catalog sat_id. Response "
            "includes utility_preview (post-burn vs no-burn catalog SGP4 over one orbit, integrated squared loss, "
            "calibration ratios vs L, verdicts, utility vs Δv budget) — cite calibration when discussing orbit cost."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sat_id": {
                    "type": "string",
                    "description": (
                        "Catalog spacecraft: primary key sat_id, or NORAD digits (e.g. 25544), or a "
                        "distinctive name substring — see get_operator_reference.catalog_entries"
                    ),
                },
                "target_circular_altitude_km": {
                    "type": "number",
                    "description": "Desired circular altitude above mean Earth radius (km)",
                },
                "reference_utc": {
                    "type": "string",
                    "description": "Optional ISO-8601 UTC instant for SGP4 state (default: now)",
                },
            },
            "required": ["sat_id", "target_circular_altitude_km"],
        },
    },
]

def openai_chat_tools() -> list[dict[str, object]]:
    """Map ``_AGENT_TOOL_SPECS`` to OpenAI Chat Completions ``tools`` format."""

    out: list[dict[str, object]] = []
    for t in _AGENT_TOOL_SPECS:
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
