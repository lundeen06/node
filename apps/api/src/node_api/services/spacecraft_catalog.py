"""Persist Space-Track GP rows and derived orbital elements."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from node_api.db.models import SpacecraftRow
from node_api.lib.geodesy import eci_m_to_lon_lat_deg
from node_api.lib.ingress.constellation_presets import PRESET_METADATA, fetch_gp_constellation
from node_api.lib.ingress.gp_elements import (
    gp_record_to_absolute_elements,
    gp_record_to_tle,
    parse_gp_epoch,
)
from node_api.lib.ingress.space_track import fetch_gp_rows
from node_api.physics_runtime import ensure_physics_importable

ensure_physics_importable()
from physics.infra.propagate_orbit import propagate_absolute_elements  # noqa: E402
from physics.infra.slate import AbsoluteOrbitalElements  # noqa: E402


def upsert_spacecraft_from_gp(
    session: Session,
    *,
    sat_id: str,
    name: str,
    norad_catalog_id: int,
    purpose: str,
    gp: dict[str, Any],
) -> SpacecraftRow:
    """Insert or update one row from a Space-Track **gp** JSON object."""
    els = gp_record_to_absolute_elements(gp)
    epoch = parse_gp_epoch(gp)
    tle = gp_record_to_tle(gp)
    display_name = name.strip() or str(gp.get("OBJECT_NAME", sat_id)).strip()
    row = SpacecraftRow(
        sat_id=sat_id,
        name=display_name,
        norad_catalog_id=norad_catalog_id,
        purpose=purpose.strip(),
        gp_snapshot_json=json.dumps(gp),
        tle_line1=tle.line1,
        tle_line2=tle.line2,
        oe_vector_json=json.dumps(list(els.as_vector())),
        ephemeris_epoch_utc=epoch,
        updated_at=datetime.now(tz=UTC),
    )
    merged = session.merge(row)
    session.commit()
    session.refresh(merged)
    return merged


def register_and_fetch(session: Session, sat_id: str, name: str, norad_catalog_id: int, purpose: str) -> SpacecraftRow:
    """Fetch latest GP from Space-Track and persist."""
    gp = fetch_gp_rows([norad_catalog_id])[0]
    return upsert_spacecraft_from_gp(
        session,
        sat_id=sat_id,
        name=name,
        norad_catalog_id=norad_catalog_id,
        purpose=purpose,
        gp=gp,
    )


def sync_all_registered(session: Session) -> int:
    """Refresh GP snapshots for every spacecraft in the database."""
    rows = list(session.scalars(select(SpacecraftRow)))
    if not rows:
        return 0
    norad_ids = [r.norad_catalog_id for r in rows]
    gps = fetch_gp_rows(norad_ids)
    by_norad: dict[int, dict[str, Any]] = {}
    for gp in gps:
        raw = gp.get("NORAD_CAT_ID")
        by_norad[int(str(raw).strip())] = gp
    count = 0
    for row in rows:
        gp = by_norad[row.norad_catalog_id]
        upsert_spacecraft_from_gp(
            session,
            sat_id=row.sat_id,
            name=row.name,
            norad_catalog_id=row.norad_catalog_id,
            purpose=row.purpose,
            gp=gp,
        )
        count += 1
    return count


def _default_purpose_for_preset(preset_id: str) -> str:
    for meta in PRESET_METADATA:
        if meta.id == preset_id:
            return f"{meta.label} constellation"
    return f"{preset_id} constellation"


def import_constellation_preset(
    session: Session,
    *,
    preset_id: str,
    limit: int,
    purpose: str,
    sat_id_prefix: str,
    timeout_s: float = 300.0,
) -> dict[str, Any]:
    """Fetch GP via name-pattern presets and upsert each object (bounded by ``limit``)."""
    key = preset_id.strip().lower()
    rows, truncated = fetch_gp_constellation(key, limit=limit, timeout_s=timeout_s)
    prefix = (sat_id_prefix.strip() or key).replace(" ", "_")[:64]
    purpose_filled = purpose.strip() or _default_purpose_for_preset(key)
    imported = 0
    skipped = 0
    for gp in rows:
        try:
            norad = int(str(gp["NORAD_CAT_ID"]).strip())
        except (KeyError, TypeError, ValueError):
            skipped += 1
            continue
        sat_id = f"{prefix}-{norad}"[:128]
        obj_name = str(gp.get("OBJECT_NAME", sat_id)).strip()
        try:
            upsert_spacecraft_from_gp(
                session,
                sat_id=sat_id,
                name=obj_name,
                norad_catalog_id=norad,
                purpose=purpose_filled,
                gp=gp,
            )
        except Exception:  # noqa: BLE001 — skip malformed GP rows
            skipped += 1
            continue
        imported += 1

    return {
        "preset": key,
        "imported": imported,
        "skipped": skipped,
        "truncated": truncated,
        "limit": limit,
    }


def spacecraft_positions_geojson(
    session: Session,
    *,
    max_count: int,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Propagate each stored mean-element set to ``now`` (ECI via physics), project to lon/lat for maps.

    Uses the same pipeline as ``GET /spacecraft/{{sat_id}}/trajectory`` (mean elements + ``propagate_oe`` / J2).
    """
    now = (now_utc or datetime.now(tz=UTC)).astimezone(UTC)
    rows = list(session.scalars(select(SpacecraftRow).order_by(SpacecraftRow.sat_id).limit(max_count)))
    features: list[dict[str, Any]] = []
    for row in rows:
        try:
            els = AbsoluteOrbitalElements.from_vector(tuple(json.loads(row.oe_vector_json)))
            ep = row.ephemeris_epoch_utc
            if ep.tzinfo is None:
                ep = ep.replace(tzinfo=UTC)
            else:
                ep = ep.astimezone(UTC)
            dt_s = (now - ep).total_seconds()
            pv = propagate_absolute_elements(els, np.array([dt_s], dtype=np.float64), use_j2=True)
            pos_m = pv[0:3, 0]
            lon, lat = eci_m_to_lon_lat_deg(pos_m, now)
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {
                        "sat_id": row.sat_id,
                        "name": row.name,
                        "norad_catalog_id": row.norad_catalog_id,
                        "purpose": row.purpose or "",
                    },
                },
            )
        except Exception:
            continue

    return {"type": "FeatureCollection", "features": features}
