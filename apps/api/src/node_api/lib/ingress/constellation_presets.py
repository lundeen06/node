"""Bounded Space-Track **gp** queries for major commercial/navigation constellations.

Predicates use Space-Track ``OBJECT_NAME`` prefix patterns: ``FIELD/text~~`` means “starts with
``text``” (the ``~~`` suffix is the wildcard operator — not ``~~text*``).
See https://www.space-track.org/documentation#/api-restApi

Patterns are heuristic: names change; refine presets if your queries miss objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from node_api.lib.ingress.space_track import query_gp

# One or more predicate path segments (each passed to ``query_gp``). Results are merged by NORAD id.
# Wildcard form matches common scripts (e.g. SLTrack): ``OBJECT_NAME/STARLINK~~``, optionally with NORAD filter.
CONSTELLATION_GP_PREDICATES: dict[str, list[str]] = {
    "starlink": ["NORAD_CAT_ID/>40000/OBJECT_NAME/STARLINK~~"],
    # Project Kuiper naming varies; broaden carefully and respect Space-Track rate limits.
    "kuiper": ["OBJECT_NAME/KUIPER~~", "OBJECT_NAME/AMAZON~~"],
    # Planet Labs uses several name families.
    "planet": [
        "OBJECT_NAME/SKYSAT~~",
        "OBJECT_NAME/FLOCK~~",
        "OBJECT_NAME/DOVE~~",
        "OBJECT_NAME/PLANET~~",
    ],
    "galileo": ["OBJECT_NAME/GALILEO~~"],
    # GPS: NAVSTAR covers most ops blocks; %20 for spaces in object names (valid GP path).
    "gps": [
        "OBJECT_NAME/NAVSTAR~~",
        "OBJECT_NAME/GPS%20BIIF~~",
        "OBJECT_NAME/GPS%20BIII~~",
    ],
}


@dataclass(frozen=True)
class ConstellationPresetMeta:
    """UI / docs metadata for one preset id."""

    id: str
    label: str
    description: str
    patterns: tuple[str, ...]


PRESET_METADATA: tuple[ConstellationPresetMeta, ...] = (
    ConstellationPresetMeta(
        id="starlink",
        label="Starlink",
        description="SpaceX Starlink (OBJECT_NAME matches STARLINK…).",
        patterns=tuple(CONSTELLATION_GP_PREDICATES["starlink"]),
    ),
    ConstellationPresetMeta(
        id="kuiper",
        label="Project Kuiper",
        description="Amazon Kuiper-related names (KUIPER… / AMAZON… heuristics).",
        patterns=tuple(CONSTELLATION_GP_PREDICATES["kuiper"]),
    ),
    ConstellationPresetMeta(
        id="planet",
        label="Planet Labs",
        description="SkySat / Flock / Dove / PLANET name families.",
        patterns=tuple(CONSTELLATION_GP_PREDICATES["planet"]),
    ),
    ConstellationPresetMeta(
        id="galileo",
        label="Galileo",
        description="EU Galileo navigation constellation.",
        patterns=tuple(CONSTELLATION_GP_PREDICATES["galileo"]),
    ),
    ConstellationPresetMeta(
        id="gps",
        label="GPS (NAVSTAR)",
        description="US GPS navigation satellites (NAVSTAR / GPS Block patterns).",
        patterns=tuple(CONSTELLATION_GP_PREDICATES["gps"]),
    ),
)


def list_preset_ids() -> list[str]:
    return sorted(CONSTELLATION_GP_PREDICATES.keys())


def require_preset(preset_id: str) -> str:
    """Normalize and validate preset key."""
    key = preset_id.strip().lower()
    if key not in CONSTELLATION_GP_PREDICATES:
        msg = f"Unknown constellation preset {preset_id!r}. Choose one of: {', '.join(list_preset_ids())}."
        raise ValueError(msg)
    return key


def fetch_gp_constellation(
    preset_id: str,
    *,
    limit: int | None,
    timeout_s: float = 300.0,
) -> tuple[list[dict[str, Any]], bool]:
    """Fetch GP rows for a preset, merging sub-queries by NORAD id.

    Returns:
        ``(rows, truncated)`` where ``truncated`` is True if ``limit`` cut the merged list.
    """
    key = require_preset(preset_id)
    merged: dict[int, dict[str, Any]] = {}
    for pred in CONSTELLATION_GP_PREDICATES[key]:
        rows = query_gp(pred, timeout_s=timeout_s)
        for row in rows:
            raw = row.get("NORAD_CAT_ID")
            try:
                nid = int(str(raw).strip())
            except (TypeError, ValueError):
                continue
            merged.setdefault(nid, row)

    all_rows = list(merged.values())
    truncated = False
    if limit is not None and len(all_rows) > limit:
        all_rows = all_rows[:limit]
        truncated = True
    return all_rows, truncated
