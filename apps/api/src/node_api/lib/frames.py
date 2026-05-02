"""Layer 1 — frames, time scales, and element conversions (stubs)."""

from __future__ import annotations

from node_api.types.common import Vector3
from node_api.types.frames import Frame, GeodeticPosition
from node_api.types.state import EquinoctialElements, KeplerianElements, StateVector
from node_api.types.time import Epoch, TimeScale


def time_convert(epoch: Epoch, to_scale: TimeScale) -> Epoch:
    """Convert an instant between time scales with explicit tagging.

    Purpose:
        Normalize ``Epoch`` tags before mixing external products (CDM, OEM, GPS).

    When to use:
        Whenever an upstream message declares a non-UTC scale.

    Prerequisites:
        ``epoch.instant`` must be timezone-aware.

    Post-checks:
        Re-validate downstream consumers expect the new ``TimeScale``.

    Returns:
        New ``Epoch`` at the same physical instant with ``to_scale``.

    Raises:
        FrameMismatchError: If conversion tables are unavailable for the pair.
    """
    raise NotImplementedError


def convert_frame(state: StateVector, to_frame: Frame) -> StateVector:
    """Rotate/translume a Cartesian state into another reference frame.

    Purpose:
        Align states for differencing, screening, or RIC burn planning.

    When to use:
        Before subtracting primary/secondary states or applying RIC burns.

    Prerequisites:
        Earth orientation data for ECI↔ECEF if that path is requested.

    Post-checks:
        Ensure output ``frame`` matches ``to_frame`` and epochs remain aligned.

    Returns:
        New ``StateVector`` with identical physical instant.

    Raises:
        FrameMismatchError: If required EOP or reference data is missing.
    """
    raise NotImplementedError


def geodetic_to_ecef(position: GeodeticPosition) -> Vector3:
    """Convert geodetic coordinates to ECEF position (km).

    Purpose:
        Place ground sites and geographic keep-out primitives in ECEF for geometry.

    When to use:
        After loading ``GeodeticPosition`` for stations or polygon keep-outs.

    Prerequisites:
        Ellipsoid parameters consistent with ``position.ellipsoid``.

    Post-checks:
        Pair with ``convert_frame`` if subsequent ops require ECI.

    Returns:
        Position vector in km in ``ECEF_ITRF``.

    Raises:
        FrameMismatchError: If ellipsoid is unsupported.
    """
    raise NotImplementedError


def elements_to_state(
    elements: KeplerianElements | EquinoctialElements,
    epoch: Epoch,
    frame: Frame,
) -> StateVector:
    """Convert classical or equinoctial elements to Cartesian state.

    Purpose:
        Seed numerical propagators or build OEM comparisons.

    When to use:
        When upstream data is element-based rather than Cartesian.

    Prerequisites:
        Elements must be osculating/mean-consistent with the intended propagator.

    Post-checks:
        Validate energy vs semi-major axis sanity before propagation.

    Returns:
        ``StateVector`` at ``epoch`` in ``frame``.

    Raises:
        FrameMismatchError: If frame conversion dependencies are missing.
    """
    raise NotImplementedError
