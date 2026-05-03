"""Space-Track TLE ingress and CDM stubs.

Live GP (general perturbations) TLE queries use HTTPS session cookies documented at
https://www.space-track.org/documentation#/api . Respect provider rate limits and terms.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import Any

import httpx

from node_api.config import settings
from node_api.errors import DataUnavailableError
from node_api.lib.ingress.gp_elements import gp_record_to_tle
from node_api.types.catalog import CDM, TLE
from node_api.types.time import Epoch

_SPACETRACK_ORIGIN = "https://www.space-track.org"

# GP query predicate reference: https://www.space-track.org/documentation#/api-restApi


def _validate_gp_predicate_path(predicates_path: str) -> None:
    """Reject obviously unsafe paths for programmatic GP queries."""
    if not predicates_path or not predicates_path.strip():
        msg = "GP predicate path must be non-empty."
        raise ValueError(msg)
    stripped = predicates_path.strip().strip("/")
    if ".." in stripped or "\n" in stripped or "\r" in stripped:
        msg = "Invalid GP predicate path."
        raise ValueError(msg)
    if len(stripped) > 512:
        msg = "GP predicate path exceeds maximum length."
        raise ValueError(msg)


class SpaceTrackClient:
    """Small synchronous Space-Track session (login → cookie → REST queries → logout)."""

    def __init__(
        self,
        identity: str,
        password: str,
        *,
        user_agent: str,
        timeout_s: float = 60.0,
    ) -> None:
        self._identity = identity
        self._password = password
        self._headers = {"User-Agent": user_agent}
        self._client = httpx.Client(base_url=_SPACETRACK_ORIGIN, headers=self._headers, timeout=timeout_s)

    def close(self) -> None:
        try:
            self._client.post("/ajaxauth/logout")
        except httpx.HTTPError:
            pass
        self._client.close()

    def __enter__(self) -> SpaceTrackClient:
        self.login()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def login(self) -> None:
        resp = self._client.post(
            "/ajaxauth/login",
            data={"identity": self._identity, "password": self._password},
        )
        if resp.status_code != httpx.codes.OK:
            msg = f"Space-Track login failed with HTTP {resp.status_code}."
            raise DataUnavailableError(msg)

    def query_gp_json(self, predicates_path: str) -> list[dict[str, Any]]:
        """Run an arbitrary **gp** (general perturbations) query.

        ``predicates_path`` is the segment between ``.../class/gp/`` and ``/format/json``.
        Examples (see Space-Track REST docs):

        - ``NORAD_CAT_ID/25544`` — latest GP row for one catalog number
        - ``NORAD_CAT_ID/25544,43852`` — several NORAD IDs
        - ``EPOCH/>now-7`` — GP updates with epoch in the last 7 days (can be large)

        Each JSON object typically includes ``OBJECT_NAME``, orbital elements,
        ``TLE_LINE1``, ``TLE_LINE2``, ``NORAD_CAT_ID``, ``EPOCH``, ``MEAN_MOTION``, etc.
        """
        _validate_gp_predicate_path(predicates_path)
        safe = predicates_path.strip().strip("/")
        url_path = f"/basicspacedata/query/class/gp/{safe}/format/json"
        resp = self._client.get(url_path)
        if resp.status_code != httpx.codes.OK:
            msg = f"Space-Track GP query failed with HTTP {resp.status_code}."
            raise DataUnavailableError(msg)
        try:
            payload = resp.json()
        except ValueError as exc:
            msg = "Space-Track GP response was not valid JSON."
            raise DataUnavailableError(msg) from exc

        if not isinstance(payload, list):
            msg = "Space-Track GP JSON root must be an array."
            raise DataUnavailableError(msg)

        out: list[dict[str, Any]] = []
        for row in payload:
            if isinstance(row, dict):
                out.append(row)
        return out

    def fetch_gp_rows(self, norad_ids: list[int]) -> list[dict[str, Any]]:
        """Latest GP JSON rows for the given NORAD catalog ids (order matches ``norad_ids``)."""
        if not norad_ids:
            return []
        unique_ids = list(dict.fromkeys(norad_ids))
        id_list = ",".join(str(i) for i in unique_ids)
        predicates = f"NORAD_CAT_ID/{id_list}"
        payload = self.query_gp_json(predicates)

        by_id: dict[int, dict[str, Any]] = {}
        for row in payload:
            raw_id = row.get("NORAD_CAT_ID")
            try:
                nid = int(str(raw_id).strip())
            except (TypeError, ValueError):
                continue
            by_id[nid] = row

        missing = [nid for nid in unique_ids if nid not in by_id]
        if missing:
            msg = f"Space-Track returned no GP data for NORAD IDs: {missing}"
            raise DataUnavailableError(msg)

        return [by_id[nid] for nid in norad_ids]

    def fetch_gp_tles(self, norad_ids: list[int]) -> list[TLE]:
        """Latest GP element sets for the given NORAD catalog numbers."""
        return [gp_record_to_tle(row) for row in self.fetch_gp_rows(norad_ids)]


@contextmanager
def spacetrack_session(
    identity: str | None = None,
    password: str | None = None,
    *,
    user_agent: str | None = None,
    timeout_s: float = 120.0,
) -> Iterator[SpaceTrackClient]:
    """Context manager wrapping :class:`SpaceTrackClient` with guaranteed logout."""
    ident = identity if identity is not None else settings.spacetrack_identity
    pwd = password if password is not None else settings.spacetrack_password
    ua = user_agent if user_agent is not None else settings.spacetrack_user_agent
    if not ident or not pwd:
        msg = (
            "Space-Track credentials are not configured. "
            "Set NODE_SPACETRACK_IDENTITY and NODE_SPACETRACK_PASSWORD."
        )
        raise DataUnavailableError(msg)

    client = SpaceTrackClient(ident, pwd, user_agent=ua, timeout_s=timeout_s)
    try:
        client.login()
        yield client
    finally:
        client.close()


def fetch_tle(norad_ids: list[int]) -> list[TLE]:
    """Retrieve latest GP TLEs from Space-Track for the requested catalog numbers.

    Requires ``NODE_SPACETRACK_IDENTITY`` and ``NODE_SPACETRACK_PASSWORD``.
    """
    if not norad_ids:
        return []
    with spacetrack_session() as client:
        return client.fetch_gp_tles(norad_ids)


def fetch_gp_rows(norad_ids: list[int]) -> list[dict[str, Any]]:
    """Same session as :func:`fetch_tle`, but returns raw **gp** JSON rows from Space-Track."""
    if not norad_ids:
        return []
    with spacetrack_session() as client:
        return client.fetch_gp_rows(norad_ids)


def query_gp(predicates_path: str, *, timeout_s: float = 120.0) -> list[dict[str, Any]]:
    """Authenticated GP query with a custom predicate path (see :meth:`SpaceTrackClient.query_gp_json`)."""
    _validate_gp_predicate_path(predicates_path)
    with spacetrack_session(timeout_s=timeout_s) as client:
        return client.query_gp_json(predicates_path)


def fetch_cdm(since_epoch: Epoch | None = None) -> list[CDM]:
    """Batch-download CDMs created after an optional watermark epoch."""
    raise NotImplementedError


async def subscribe_cdm_stream() -> AsyncIterator[CDM]:
    """Push-mode CDM subscription (stub; production form will be an async iterator)."""
    msg = "subscribe_cdm_stream is not implemented."
    raise NotImplementedError(msg)
