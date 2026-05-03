"""In-memory mock data registry for agent tools.

Keyed to match the frontend mock data (MOCK_SATELLITES, MOCK_CONJUNCTION, MOCK_AGENT_PLAN).
Replace with real lib function calls once physics stubs are implemented.
"""

from __future__ import annotations

from typing import Any

SATELLITES: dict[str, dict[str, Any]] = {
    "EO-12": {
        "sat_id": "EO-12",
        "constellation_id": "EO-CONSTELLATION",
        "fuel_kg": 12.3,
        "data_quality": "NOMINAL",
        "last_updated_utc": "2026-05-02T14:20:00Z",
    },
    "REL-3": {
        "sat_id": "REL-3",
        "constellation_id": "EO-CONSTELLATION",
        "fuel_kg": 8.7,
        "data_quality": "NOMINAL",
        "last_updated_utc": "2026-05-02T14:18:00Z",
    },
    "SKY-1": {
        "sat_id": "SKY-1",
        "constellation_id": "EO-CONSTELLATION",
        "fuel_kg": 5.2,
        "data_quality": "DEGRADED",
        "last_updated_utc": "2026-05-02T14:05:00Z",
    },
}

CONJUNCTIONS: dict[str, dict[str, Any]] = {
    "CJX-2041": {
        "id": "CJX-2041",
        "primary_id": "EO-12",
        "secondary_id": "DEB-49811",
        "tca_utc": "2026-05-02T16:04:12Z",
        "miss_distance_km": 0.62,
        "relative_velocity_km_s": 14.8,
        "pc": 2.3e-4,
        "pc_method": "FOSTER",
        "source": "CDM",
        "status": "NEW",
    },
}

HOUSE_RULES: dict[str, dict[str, Any]] = {
    "EO-CONSTELLATION": {
        "constellation_id": "EO-CONSTELLATION",
        "pc_mitigation_threshold": 1e-4,
        "max_auto_delta_v_mps": 0.1,
    },
}

PLANS: dict[str, dict[str, Any]] = {
    "CJX-2041": {
        "plan_id": "plan-cjx-2041-001",
        "sat_id": "EO-12",
        "maneuvers": [
            {
                "epoch_utc": "2026-05-02T15:10:00Z",
                "delta_v_mps": {"x": 0.052, "y": -0.011, "z": 0.004},
                "frame": "RIC",
                "duration_s": 8.0,
            }
        ],
        "total_delta_v_mps": 0.054,
        "objective": (
            "Reduce Pc from 2.3e-4 to below 1e-4 with minimal in-track cost; "
            "preserve ground contacts GS-12 and GS-04."
        ),
        "generated_by": "AGENT",
        "validation": [
            {
                "check_id": "induced_conjunctions",
                "passed": True,
                "message": "No new close approaches introduced.",
            },
            {
                "check_id": "fuel_compliance",
                "passed": True,
                "message": "0.054 m/s uses 0.002 kg; 12.3 kg reserve maintained.",
            },
            {
                "check_id": "keep_out_compliance",
                "passed": True,
                "message": "Post-maneuver trajectory clears all keep-out zones.",
            },
        ],
    },
}
