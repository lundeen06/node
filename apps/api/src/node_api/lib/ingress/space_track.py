"""Space-Track–style TLE/CDM ingress (stubs)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from node_api.types.catalog import CDM, TLE
from node_api.types.time import Epoch


def fetch_tle(norad_ids: list[int]) -> list[TLE]:
    """Retrieve latest TLEs for the requested catalog numbers.

    Purpose:
        Pull authoritative element sets for propagation and screening.

    When to use:
        After identifying target NORAD IDs from conjunction messages or fleet cross-links.

    Prerequisites:
        Valid network credentials configured for the upstream provider (not modeled here).

    Post-checks:
        - Validate line checksums before calling ``propagate_sgp4``.
        - Compare TLE epoch age against ``HouseRules`` staleness limits.

    Returns:
        One ``TLE`` per requested id that exists in the catalog feed.

    Raises:
        DataUnavailableError: If the provider is unreachable or returns partial data.
    """
    raise NotImplementedError


def fetch_cdm(since_epoch: Epoch | None = None) -> list[CDM]:
    """Batch-download CDMs created after an optional watermark epoch.

    Purpose:
        Ingest conjunction warnings for operator review and automated screening.

    When to use:
        On a polling cadence or after a provider webhook signals new messages.

    Prerequisites:
        ``since_epoch`` should be the last successfully processed creation time.

    Post-checks:
        - Parse and validate participant ids against internal satellite registry.
        - Route high-Pc events to ``compute_pc`` / mission planners.

    Returns:
        Chronologically sorted CDM records.

    Raises:
        DataUnavailableError: If the feed errors or authentication fails.
    """
    raise NotImplementedError


async def subscribe_cdm_stream() -> AsyncIterator[CDM]:
    """Push-mode CDM subscription (stub; production form will be an async iterator).

    Purpose:
        Stream conjunction messages as they are published for low-latency ops.

    When to use:
        When polling latency is unacceptable for high-risk assets.

    Prerequisites:
        Persistent session credentials and reconnect policy configured externally.

    Post-checks:
        Same as ``fetch_cdm`` for each yielded record.

    Returns:
        Async iterator of ``CDM`` objects.

    Raises:
        DataUnavailableError: If the stream cannot be established.
    """
    msg = "subscribe_cdm_stream is not implemented."
    raise NotImplementedError(msg)
    # Mypy: annotated as AsyncIterator for the future streaming API surface.
