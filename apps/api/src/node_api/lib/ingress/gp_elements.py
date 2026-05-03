"""Space-Track GP JSON → :class:`physics.infra.slate.AbsoluteOrbitalElements` + epoch."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from typing import Any

from node_api.errors import DataUnavailableError
from node_api.physics_runtime import ensure_physics_importable
from node_api.types.catalog import TLE
from node_api.types.time import Epoch, TimeScale

ensure_physics_importable()
from physics.infra.slate import AbsoluteOrbitalElements  # noqa: E402

_MU_EARTH_M3_S2 = 3.986004415e14


def parse_gp_epoch(record: dict[str, Any]) -> datetime:
    """Parse Space-Track ``EPOCH`` field to timezone-aware UTC."""
    raw = record.get("EPOCH")
    if raw is None:
        msg = "GP record has no EPOCH field."
        raise DataUnavailableError(msg)
    s = str(raw).strip()
    if not s:
        msg = "GP EPOCH field is empty."
        raise DataUnavailableError(msg)
    try:
        isoish = s.replace(" ", "T", 1)
        if re.search(r"[+-]\d{2}:\d{2}$", isoish) is None and isoish.endswith("Z") is False:
            isoish = isoish + "+00:00"
        dt = datetime.fromisoformat(isoish.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(s[:26], fmt).replace(tzinfo=UTC)
                break
            except ValueError:
                continue
        else:
            msg = f"Could not parse GP EPOCH: {s!r}"
            raise DataUnavailableError(msg) from None
    else:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        else:
            dt = dt.astimezone(UTC)
    return dt


def _f(record: dict[str, Any], key: str) -> float:
    try:
        return float(str(record[key]).strip())
    except (KeyError, TypeError, ValueError) as exc:
        msg = f"GP record missing or invalid numeric field {key!r}."
        raise DataUnavailableError(msg) from exc


def _eccentricity(record: dict[str, Any]) -> float:
    """Parse ECCENTRICITY; Space-Track sometimes zero-pads a fractional form (e.g. ``0007418`` → 0.0007418)."""
    try:
        raw = str(record["ECCENTRICITY"]).strip()
    except KeyError as exc:
        msg = "GP record missing ECCENTRICITY."
        raise DataUnavailableError(msg) from exc
    v = float(raw)
    if v < 1.0:
        return v
    digits = raw.split(".", 1)[0]
    num = int(digits.lstrip("0") or "0")
    return float(num / (10 ** max(len(digits), 1)))


def gp_record_to_absolute_elements(record: dict[str, Any]) -> AbsoluteOrbitalElements:
    """Build classical elements (``a`` in m, angles in rad) from a Space-Track **gp** row."""
    if "SEMIMAJOR_AXIS" in record and record["SEMIMAJOR_AXIS"] not in (None, ""):
        a_m = _f(record, "SEMIMAJOR_AXIS") * 1000.0
    else:
        n_rev_per_day = _f(record, "MEAN_MOTION")
        n_rad_s = n_rev_per_day * (2.0 * math.pi) / 86400.0
        if n_rad_s <= 0:
            msg = "MEAN_MOTION must be positive."
            raise DataUnavailableError(msg)
        a_m = (_MU_EARTH_M3_S2 / (n_rad_s**2)) ** (1.0 / 3.0)

    e = _eccentricity(record)
    inc_deg = _f(record, "INCLINATION")
    raan_deg = _f(record, "RA_OF_ASC_NODE")
    argp_deg = _f(record, "ARG_OF_PERICENTER")
    ma_deg = _f(record, "MEAN_ANOMALY")

    deg = math.pi / 180.0
    return AbsoluteOrbitalElements(
        semi_major_axis_m=a_m,
        eccentricity=e,
        inclination_rad=inc_deg * deg,
        raan_rad=raan_deg * deg,
        arg_perigee_rad=argp_deg * deg,
        mean_anomaly_rad=ma_deg * deg,
    )


def gp_record_to_tle(record: dict[str, Any]) -> TLE:
    """Build domain :class:`TLE` using GP epoch (no Skyfield)."""
    try:
        line1 = str(record["TLE_LINE1"]).strip()
        line2 = str(record["TLE_LINE2"]).strip()
        norad_id = int(str(record["NORAD_CAT_ID"]).strip())
    except (KeyError, TypeError, ValueError) as exc:
        msg = "GP row missing TLE_LINE1, TLE_LINE2, or NORAD_CAT_ID."
        raise DataUnavailableError(msg) from exc

    epoch_dt = parse_gp_epoch(record)
    epoch = Epoch(instant=epoch_dt, scale=TimeScale.UTC)
    return TLE(line1=line1, line2=line2, epoch=epoch, satellite_number=norad_id)
