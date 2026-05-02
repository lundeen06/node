"""Celestrak-style catalog snapshots (stubs)."""

from __future__ import annotations

from node_api.types.catalog import CatalogObject


def fetch_celestrak_snapshot(group: str) -> list[CatalogObject]:
    """Download a named Celestrak supplement group as normalized catalog objects.

    Purpose:
        Bulk-ingest public TLE groups (e.g. ``active``, ``stations``) for screening.

    When to use:
        When Space-Track credentials are unavailable but public groups suffice.

    Prerequisites:
        Network egress to the public endpoint.

    Post-checks:
        - Deduplicate against internal registry by NORAD id.
        - Stamp ``latest_state`` provenance with ``source="CELESTRAK"``.

    Returns:
        ``CatalogObject`` rows suitable for ``screen_catalog_against_ego``.

    Raises:
        DataUnavailableError: If the named group cannot be retrieved.
    """
    raise NotImplementedError
