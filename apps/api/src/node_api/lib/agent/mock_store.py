"""In-memory mock data for agent tools where persistence is not yet wired.

Conjunction events come from SQLite via catalog screening (see ``conjunction_store``).
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

HOUSE_RULES: dict[str, dict[str, Any]] = {
    "EO-CONSTELLATION": {
        "constellation_id": "EO-CONSTELLATION",
        "pc_mitigation_threshold": 1e-4,
        "max_auto_delta_v_mps": 800.0,
    },
    "CATALOG-DEFAULT": {
        "constellation_id": "CATALOG-DEFAULT",
        "pc_mitigation_threshold": 1e-3,
        "max_auto_delta_v_mps": 800.0,
    },
}
