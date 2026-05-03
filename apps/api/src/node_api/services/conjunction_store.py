"""Persist catalog-screen conjunction hits for agent tools and ops continuity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from node_api.db.models import ConjunctionEventRow


def replace_catalog_conjunction_snapshot(session: Session, raw: list[dict[str, Any]]) -> None:
    """Replace stored events with the latest catalog-screen batch (demo snapshot)."""
    session.execute(delete(ConjunctionEventRow))
    now = datetime.now(UTC)
    for e in raw:
        tca = datetime.fromisoformat(str(e["tca_utc"]).replace("Z", "+00:00"))
        session.add(
            ConjunctionEventRow(
                id=str(e["id"]),
                primary_id=str(e["primary_sat_id"]),
                secondary_id=str(e["secondary_sat_id"]),
                tca_utc=tca,
                miss_distance_km=float(e["miss_distance_km"]),
                relative_velocity_km_s=0.0,
                pc=float(e["pc_heuristic"]),
                pc_method="SCREEN_HEURISTIC",
                source="CATALOG_SCREEN",
                status="NEW",
                created_at=now,
            ),
        )


def conjunction_row_to_tool_dict(row: ConjunctionEventRow) -> dict[str, Any]:
    tca = row.tca_utc.astimezone(UTC)
    return {
        "id": row.id,
        "primary_id": row.primary_id,
        "secondary_id": row.secondary_id,
        "tca_utc": tca.isoformat().replace("+00:00", "Z"),
        "miss_distance_km": row.miss_distance_km,
        "relative_velocity_km_s": row.relative_velocity_km_s,
        "pc": row.pc,
        "pc_method": row.pc_method,
        "source": row.source,
        "status": row.status,
    }


def list_active_conjunctions_for_sat(
    session: Session,
    *,
    sat_id: str,
    horizon_hours: int,
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    horizon_end = now + timedelta(hours=max(1, horizon_hours))
    stmt = (
        select(ConjunctionEventRow)
        .where(
            or_(
                ConjunctionEventRow.primary_id == sat_id,
                ConjunctionEventRow.secondary_id == sat_id,
            ),
            ConjunctionEventRow.status.in_(("NEW", "ACKNOWLEDGED")),
            ConjunctionEventRow.tca_utc >= now,
            ConjunctionEventRow.tca_utc <= horizon_end,
        )
        .order_by(ConjunctionEventRow.tca_utc)
    )
    rows = list(session.scalars(stmt))
    return [conjunction_row_to_tool_dict(r) for r in rows]


def get_conjunction_by_id(session: Session, conjunction_id: str) -> ConjunctionEventRow | None:
    return session.get(ConjunctionEventRow, conjunction_id)


def upsert_operator_conjunction_context(session: Session, cc: dict[str, Any]) -> None:
    """Merge UI-selected conjunction into SQLite so agent tools resolve it for this turn."""
    cid = cc.get("conjunction_id")
    if not cid or not isinstance(cid, str):
        return
    pid = cc.get("primary_sat_id")
    sid = cc.get("secondary_sat_id")
    if not pid or not sid:
        return
    tca_raw = cc.get("tca_utc")
    if not tca_raw:
        return
    try:
        tca = datetime.fromisoformat(str(tca_raw).replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return
    miss = float(cc["miss_distance_km"]) if cc.get("miss_distance_km") is not None else 0.0
    pc = float(cc["pc_heuristic"]) if cc.get("pc_heuristic") is not None else 0.0
    now = datetime.now(UTC)
    session.merge(
        ConjunctionEventRow(
            id=cid,
            primary_id=str(pid),
            secondary_id=str(sid),
            tca_utc=tca,
            miss_distance_km=miss,
            relative_velocity_km_s=0.0,
            pc=pc,
            pc_method="SCREEN_HEURISTIC",
            source=str(cc.get("source") or "CATALOG_SCREEN"),
            status="NEW",
            created_at=now,
        ),
    )
    session.commit()


def list_all_active_conjunctions(
    session: Session,
    *,
    horizon_hours: int,
) -> list[dict[str, Any]]:
    """All persisted events in the forward window (any pair in the latest catalog snapshot)."""
    now = datetime.now(UTC)
    horizon_end = now + timedelta(hours=max(1, horizon_hours))
    stmt = (
        select(ConjunctionEventRow)
        .where(
            ConjunctionEventRow.status.in_(("NEW", "ACKNOWLEDGED")),
            ConjunctionEventRow.tca_utc >= now,
            ConjunctionEventRow.tca_utc <= horizon_end,
        )
        .order_by(ConjunctionEventRow.tca_utc)
    )
    rows = list(session.scalars(stmt))
    return [conjunction_row_to_tool_dict(r) for r in rows]
