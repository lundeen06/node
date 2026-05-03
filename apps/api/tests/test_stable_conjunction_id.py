"""Stable catalog-screen conjunction IDs (agent + SQLite continuity)."""

from __future__ import annotations

from datetime import UTC, datetime

from node_api.services.catalog_conjunction_screen import stable_catalog_conjunction_event_id


def test_stable_id_invariant_to_primary_secondary_order() -> None:
    t = datetime(2026, 5, 3, 12, 24, 4, tzinfo=UTC)
    a = stable_catalog_conjunction_event_id("00-EGO", "00-TGT", t)
    b = stable_catalog_conjunction_event_id("00-TGT", "00-EGO", t)
    assert a == b
    assert a.startswith("CNJ-")
    assert len(a) == 14


def test_stable_id_same_five_minute_bucket() -> None:
    t0 = datetime(2026, 5, 3, 12, 24, 4, tzinfo=UTC)
    t1 = t0.replace(second=59)
    a = stable_catalog_conjunction_event_id("A", "B", t0)
    b = stable_catalog_conjunction_event_id("A", "B", t1)
    assert a == b
