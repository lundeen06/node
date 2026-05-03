"""Coarse catalog-wide conjunction screening for ops demos (SGP4 pairwise)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from node_api.db.models import SpacecraftRow
from node_api.lib.pair_conjunction_sgp4 import screen_pair_sphere_sgp4
from node_api.lib.tle_physics import sgp4_position_eci_m
from node_api.lib.trajectory_maneuver_preview import trajectory_preview_maneuvers_m

# TCA bucket size (seconds) for stable IDs across catalog-screen re-runs (same pair + window → same CNJ id).
_STABLE_CNJ_TCA_BUCKET_S = 300


def stable_catalog_conjunction_event_id(primary_sat_id: str, secondary_sat_id: str, tca_utc: datetime) -> str:
    """Deterministic event id so SQLite survives periodic re-screening without invalidating agent/UI refs."""
    a, b = sorted((primary_sat_id, secondary_sat_id))
    t_bucket = int(tca_utc.astimezone(UTC).timestamp() // _STABLE_CNJ_TCA_BUCKET_S)
    raw = f"{a}\x00{b}\x00{t_bucket}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10].upper()
    return f"CNJ-{digest}"


def _position_km_m(row: SpacecraftRow, when_utc: datetime) -> np.ndarray:
    return np.asarray(sgp4_position_eci_m(row.tle_line1, row.tle_line2, when_utc), dtype=np.float64) / 1000.0


def _maneuver_position_eci_m_at(
    line1: str,
    line2: str,
    burns: list[tuple[datetime, np.ndarray]],
    when_utc: datetime,
) -> np.ndarray:
    """ECI position (m) on the maneuver-preview polyline at ``when_utc`` (same model as trajectory-preview API)."""
    t = when_utc.astimezone(UTC)
    times = [t - timedelta(seconds=90), t - timedelta(seconds=45), t, t + timedelta(seconds=45), t + timedelta(seconds=90)]
    raw = trajectory_preview_maneuvers_m(line1, line2, times, burns)
    when_ms = t.timestamp() * 1000.0
    best: tuple[float, np.ndarray] | None = None
    for tt, pos_m, _vel in raw:
        dt = abs((tt.timestamp() * 1000.0) - when_ms)
        if best is None or dt < best[0]:
            best = (dt, np.asarray(pos_m, dtype=np.float64).reshape(3))
    if best is None:
        msg = "maneuver preview returned no samples"
        raise ValueError(msg)
    return best[1]


def refine_catalog_events_with_maneuver_preview(
    session: Session,
    events: list[dict[str, Any]],
    *,
    maneuver_sat_id: str,
    burns: list[tuple[datetime, np.ndarray]],
) -> list[dict[str, Any]]:
    """Re-check each event involving ``maneuver_sat_id`` at TCA using preview trajectory; drop mitigated hits.

    Catalog TLEs are **not** rewritten; this only adjusts screening output to match the same preview physics as the globe.
    """
    row_m = session.get(SpacecraftRow, maneuver_sat_id)
    if row_m is None or not burns:
        return events
    out: list[dict[str, Any]] = []
    for ev in events:
        pid = str(ev["primary_sat_id"])
        sid = str(ev["secondary_sat_id"])
        if maneuver_sat_id not in (pid, sid):
            out.append(ev)
            continue
        other_id = sid if maneuver_sat_id == pid else pid
        row_o = session.get(SpacecraftRow, other_id)
        if row_o is None:
            out.append(ev)
            continue
        try:
            tca = datetime.fromisoformat(str(ev["tca_utc"]).replace("Z", "+00:00")).astimezone(UTC)
            # Nominal TCA can fall **before** a mitigation burn; at TCA the preview is still pre-burn, so
            # separation would wrongly look risky. Evaluate after the last burn when it is after TCA.
            latest_burn = max((b[0] for b in burns), default=None)
            if latest_burn is not None and latest_burn > tca:
                t_eval = latest_burn + timedelta(seconds=45)
            else:
                t_eval = tca
            r_m_m = _maneuver_position_eci_m_at(row_m.tle_line1, row_m.tle_line2, burns, t_eval)
            r_o_km = _position_km_m(row_o, t_eval)
            r_o_m = r_o_km * 1000.0
        except Exception:
            out.append(ev)
            continue
        sep_km = float(np.linalg.norm(r_m_m - r_o_m)) / 1000.0
        R = float(ev["sphere_radius_km"])
        if sep_km > R:
            continue
        if maneuver_sat_id == pid:
            pri_m, sec_m = r_m_m, r_o_m
        else:
            pri_m, sec_m = r_o_m, r_m_m
        mid_m = (pri_m + sec_m) * 0.5
        mid = (float(mid_m[0]), float(mid_m[1]), float(mid_m[2]))
        pm = (float(pri_m[0]), float(pri_m[1]), float(pri_m[2]))
        sm = (float(sec_m[0]), float(sec_m[1]), float(sec_m[2]))
        old_miss = float(ev["miss_distance_km"])
        old_pc = float(ev["pc_heuristic"])
        scale = min(1.0, sep_km / max(old_miss, 1e-9)) if old_miss > 0 else 1.0
        pc_new = min(old_pc, old_pc * scale + 1e-12)
        out.append(
            {
                **ev,
                "miss_distance_km": sep_km,
                "pc_heuristic": float(np.clip(pc_new, 0.0, 1.0)),
                "eci_mid_m": list(mid),
                "primary_eci_m": list(pm),
                "secondary_eci_m": list(sm),
            },
        )
    return out


def screen_catalog_close_approaches(
    session: Session,
    *,
    sim_utc: datetime,
    separation_prefilter_km: float = 4000.0,
    max_satellites: int = 100,
    max_candidate_pairs: int = 2500,
    sphere_radius_km: float = 10.0,
    step_s: float = 90.0,
    search_max_orbits: int = 2,
    followup_orbits: int = 2,
    maneuver_preview: tuple[str, list[tuple[datetime, np.ndarray]]] | None = None,
) -> list[dict[str, Any]]:
    """Return close-approach events (SGP4 keep-out) for a bounded subset of the catalog.

    Uses a distance prefilter at ``sim_utc`` then :func:`screen_pair_sphere_sgp4` per candidate pair.
    """
    t0 = sim_utc.astimezone(UTC)
    rows = list(
        session.scalars(select(SpacecraftRow).order_by(SpacecraftRow.sat_id).limit(max_satellites)),
    )
    if len(rows) < 2:
        return []

    pos_km: list[np.ndarray] = []
    usable: list[SpacecraftRow] = []
    for row in rows:
        try:
            pos_km.append(_position_km_m(row, t0))
            usable.append(row)
        except Exception:
            continue
    if len(usable) < 2:
        return []

    n = len(usable)
    candidates: list[tuple[int, int]] = []
    full = False
    for i in range(n):
        if full:
            break
        for j in range(i + 1, n):
            d = float(np.linalg.norm(pos_km[i] - pos_km[j]))
            if d <= separation_prefilter_km:
                candidates.append((i, j))
                if len(candidates) >= max_candidate_pairs:
                    full = True
                    break

    events: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for i, j in candidates:
        a, b = usable[i], usable[j]
        key = (a.sat_id, b.sat_id) if a.sat_id < b.sat_id else (b.sat_id, a.sat_id)
        if key in seen:
            continue
        try:
            r = screen_pair_sphere_sgp4(
                a.tle_line1,
                a.tle_line2,
                b.tle_line1,
                b.tle_line2,
                t0,
                sphere_radius_km=sphere_radius_km,
                step_s=step_s,
                search_max_orbits=search_max_orbits,
                followup_orbits=followup_orbits,
            )
        except (ValueError, Exception):
            continue
        if not r.conjunction_occurred or r.first_entry_utc is None:
            continue
        seen.add(key)
        tca = r.first_entry_utc.astimezone(UTC)
        try:
            pa = _position_km_m(a, tca)
            pb = _position_km_m(b, tca)
            mid_km = (pa + pb) * 0.5
            eci_mid_m = (float(mid_km[0] * 1000.0), float(mid_km[1] * 1000.0), float(mid_km[2] * 1000.0))
            primary_m = (float(pa[0] * 1000.0), float(pa[1] * 1000.0), float(pa[2] * 1000.0))
            secondary_m = (float(pb[0] * 1000.0), float(pb[1] * 1000.0), float(pb[2] * 1000.0))
        except Exception:
            continue

        eid = stable_catalog_conjunction_event_id(a.sat_id, b.sat_id, tca)
        events.append(
            {
                "id": eid,
                "primary_sat_id": a.sat_id,
                "secondary_sat_id": b.sat_id,
                "tca_utc": tca.isoformat().replace("+00:00", "Z"),
                "miss_distance_km": r.closest_approach_km,
                "pc_heuristic": r.probability_heuristic,
                "sphere_radius_km": sphere_radius_km,
                "eci_mid_m": list(eci_mid_m),
                "primary_eci_m": list(primary_m),
                "secondary_eci_m": list(secondary_m),
            },
        )
    if maneuver_preview is not None:
        msat, br = maneuver_preview
        events = refine_catalog_events_with_maneuver_preview(session, events, maneuver_sat_id=msat, burns=br)
    return events
