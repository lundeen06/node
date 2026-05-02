"""Layer 4 — environment geometry: passes, eclipses, sun, thermal, radiation, keep-outs (stubs)."""

from __future__ import annotations

from node_api.types.common import Interval
from node_api.types.satellite import GeometricScreenResult, KeepOutZone
from node_api.types.state import StateVector
from node_api.types.trajectory import (
    EclipseInterval,
    GroundPass,
    HeatLoadSample,
    RadiationDoseSample,
    SunAngleSample,
)


def find_ground_passes(sat_id: str, station_ids: list[str], interval: Interval) -> list[GroundPass]:
    """Predict ground station visibility intervals.

    Purpose:
        Schedule contacts and downlink opportunities.

    When to use:
        After numerical propagation establishes an ephemeris arc over ``interval``.

    Prerequisites:
        ``GroundStation`` min-elevation masks loaded for each ``station_id``.

    Post-checks:
        Cross-check against ``OperationalBox`` / power constraints before uplink.

    Returns:
        List of ``GroundPass`` windows.

    Raises:
        DataUnavailableError: If station metadata is missing.
    """
    raise NotImplementedError


def find_eclipse_intervals(sat_id: str, interval: Interval) -> list[EclipseInterval]:
    """Find umbra/penumbra intervals for a satellite.

    Purpose:
        Thermal and power budgeting for maneuver timing.

    When to use:
        When maneuvers should avoid eclipse transitions or leverage them for cooling.

    Prerequisites:
        High-enough fidelity ephemeris for the shadow model in force.

    Post-checks:
        Correlate with ``estimate_thermal_exposure`` peaks.

    Returns:
        ``EclipseInterval`` list sorted by start time.

    Raises:
        FrameMismatchError: If Sun/Earth geometry inputs are unavailable.
    """
    raise NotImplementedError


def compute_sun_angle_profile(
    state: StateVector,
    interval: Interval,
    step_s: float,
) -> list[SunAngleSample]:
    """Sample sun angles along a short propagated arc (stub contract).

    Purpose:
        Support thermal and array pointing risk reviews.

    When to use:
        After ``propagate_numerical`` for segments where beta angle matters.

    Prerequisites:
        ``step_s`` > 0 and interval fits mission cache policies.

    Post-checks:
        Feed extremes into ``estimate_thermal_exposure`` / ``estimate_radiation_exposure``.

    Returns:
        Time series of ``SunAngleSample``.

    Raises:
        FrameMismatchError: If Sun ephemeris cannot be aligned to ``state.frame``.
    """
    raise NotImplementedError


def estimate_thermal_exposure(sat_id: str, interval: Interval) -> list[HeatLoadSample]:
    """Produce a coarse thermal load profile (implementation-defined).

    Purpose:
        Guard maneuver timing near thermal limits.

    When to use:
        When spacecraft has narrow safe temperature bands during high beta.

    Prerequisites:
        ``find_eclipse_intervals`` and ``compute_sun_angle_profile`` typically precede.

    Post-checks:
        Compare peaks against vehicle qualification limits (external table).

    Returns:
        ``HeatLoadSample`` series.

    Raises:
        DataUnavailableError: If vehicle thermal model parameters are missing.
    """
    raise NotImplementedError


def estimate_radiation_exposure(sat_id: str, interval: Interval) -> list[RadiationDoseSample]:
    """Produce a coarse radiation dose profile (implementation-defined).

    Purpose:
        Avoid cumulative dose violations during long thruster arcs.

    When to use:
        For MEO/GEO orbits with long SAA-like exposure (mission-specific).

    Prerequisites:
        ``SpaceWeatherState`` may be required for flux models.

    Post-checks:
        Compare against lifetime dose budgets.

    Returns:
        ``RadiationDoseSample`` series.

    Raises:
        DataUnavailableError: If environment tables are missing.
    """
    raise NotImplementedError


def check_geometric_keep_out(
    state: StateVector,
    zones: list[KeepOutZone],
) -> GeometricScreenResult:
    """Evaluate instantaneous geometric keep-out violations.

    Purpose:
        Hard safety gate before approving maneuvers that skirt exclusion volumes.

    When to use:
        After predicting ``predicted_post_state`` for a candidate plan.

    Prerequisites:
        ``zones`` expressed in frames compatible with ``state`` or convertible.

    Post-checks:
        If non-compliant, reject plan or call avoidance solvers with tightened constraints.

    Returns:
        ``GeometricScreenResult`` with compliance flag.

    Raises:
        FrameMismatchError: If a zone frame cannot be resolved.
    """
    raise NotImplementedError
