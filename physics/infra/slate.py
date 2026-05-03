"""Simulation slate: one record per spacecraft with absolute classical orbital elements.

Element order matches :func:`physics.propulsion.util_dyn.propagate_oe`::

    oe = [a, e, i, Ω, ω, M]

with ``a`` in meters (Earth-centered inertial frame), angles in radians, and eccentric
orbits implicitly elliptic ``e < 1`` for propagation helpers in ``util_dyn``.

Use ``numpy.asarray(row.elements.as_vector())`` when calling NumPy-based propagators.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterator, MutableMapping, Sequence

OrbitalElementVector = tuple[float, float, float, float, float, float]


@dataclass(frozen=True)
class AbsoluteOrbitalElements:
    """Absolute (inertial) classical Keplerian elements for one object."""

    semi_major_axis_m: float
    eccentricity: float
    inclination_rad: float
    raan_rad: float  # Ω, right ascension of ascending node
    arg_perigee_rad: float  # ω, argument of perigee
    mean_anomaly_rad: float  # M

    def as_vector(self) -> OrbitalElementVector:
        """Six-tuple in the same order as ``propagate_oe`` (``a`` in m, angles in rad)."""

        return (
            self.semi_major_axis_m,
            self.eccentricity,
            self.inclination_rad,
            self.raan_rad,
            self.arg_perigee_rad,
            self.mean_anomaly_rad,
        )

    @classmethod
    def from_vector(cls, oe: Sequence[float]) -> AbsoluteOrbitalElements:
        seq = tuple(float(x) for x in oe)
        if len(seq) != 6:
            raise ValueError("Expected classical elements [a, e, i, Ω, ω, M] (length 6).")
        return cls(
            semi_major_axis_m=seq[0],
            eccentricity=seq[1],
            inclination_rad=seq[2],
            raan_rad=seq[3],
            arg_perigee_rad=seq[4],
            mean_anomaly_rad=seq[5],
        )


@dataclass(frozen=True)
class SatelliteRecord:
    """Spacecraft identity and optional catalog hooks for filtering and reporting."""

    sat_id: str
    name: str = ""
    norad_catalog_id: int | None = None
    purpose: str = ""


@dataclass(frozen=True)
class SatelliteOnSlate:
    """One satellite together with its absolute orbital elements."""

    satellite: SatelliteRecord
    elements: AbsoluteOrbitalElements


class Slate(MutableMapping[str, SatelliteOnSlate]):
    """Mapping ``sat_id`` → satellite + absolute elements for orbit / conjunction code."""

    def __init__(self, entries: dict[str, SatelliteOnSlate] | None = None) -> None:
        self._entries: dict[str, SatelliteOnSlate] = {}
        if entries:
            for sat_id, row in entries.items():
                self[sat_id] = row

    def __getitem__(self, sat_id: str) -> SatelliteOnSlate:
        return self._entries[sat_id]

    def __setitem__(self, sat_id: str, value: SatelliteOnSlate) -> None:
        if sat_id != value.satellite.sat_id:
            raise ValueError("Key must match SatelliteRecord.sat_id.")
        self._entries[sat_id] = value

    def __delitem__(self, sat_id: str) -> None:
        del self._entries[sat_id]

    def __iter__(self) -> Iterator[str]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def put(self, row: SatelliteOnSlate) -> None:
        self[row.satellite.sat_id] = row

    def replace_elements(self, sat_id: str, elements: AbsoluteOrbitalElements) -> None:
        current = self._entries[sat_id]
        self._entries[sat_id] = replace(current, elements=elements)

    def element_vectors(self) -> dict[str, OrbitalElementVector]:
        return {sid: row.elements.as_vector() for sid, row in self._entries.items()}


__all__ = [
    "AbsoluteOrbitalElements",
    "OrbitalElementVector",
    "SatelliteRecord",
    "SatelliteOnSlate",
    "Slate",
]
