"""Layer 2 — trajectory propagation (stubs)."""

from __future__ import annotations

from typing import NewType

from node_api.types.catalog import TLE
from node_api.types.common import Interval
from node_api.types.state import Covariance6x6, StateVector
from node_api.types.trajectory import Trajectory

ForceModelHandle = NewType("ForceModelHandle", str)


def build_force_model(sat_id: str, include_drag: bool, include_srp: bool) -> ForceModelHandle:
    """Assemble a numerical force model handle for a satellite.

    Purpose:
        Bind drag/SRP toggles to a propagator configuration without exposing solver details.

    When to use:
        Before ``propagate_numerical`` or ``propagate_with_uncertainty``.

    Prerequisites:
        ``Satellite`` physical properties must be on file for area/mass.

    Post-checks:
        None intrinsic; caller validates energy drift in acceptance tests.

    Returns:
        Opaque handle consumed only by propagation routines.

    Raises:
        DataUnavailableError: If satellite parameters are incomplete.
    """
    raise NotImplementedError


def propagate_sgp4(tle: TLE, interval: Interval) -> Trajectory:
    """Propagate a TLE using an SGP4-class analytic theory.

    Purpose:
        Fast screening and visualization for LEO catalog objects.

    When to use:
        When the object is represented by a TLE and accuracy trades favor speed.

    Prerequisites:
        ``tle`` checksum-validated; ``interval`` within reasonable extrapolation policy.

    Post-checks:
        Compare against OEM if available; upgrade to numerical if discrepancies exceed threshold.

    Returns:
        ``Trajectory`` samples in provider-native frame (typically TEME).

    Raises:
        FrameMismatchError: If frame tagging cannot be completed.
    """
    raise NotImplementedError


def propagate_numerical(
    state: StateVector,
    interval: Interval,
    force_model: ForceModelHandle,
) -> Trajectory:
    """High-fidelity numerical propagation with a configured force model.

    Purpose:
        Mission-critical state prediction for maneuver planning and Pc.

    When to use:
        When SGP4 fidelity is insufficient (GEO, MEO, high-precision LEO).

    Prerequisites:
        ``build_force_model`` and optionally ``fetch_eop_series`` for ECEF coupling.

    Post-checks:
        ``check_induced_conjunctions`` after maneuver planning on the output arc.

    Returns:
        Dense or adaptive ``Trajectory`` in the input state's frame family.

    Raises:
        FrameMismatchError: If force model and state frames disagree.
    """
    raise NotImplementedError


def propagate_with_uncertainty(
    state: StateVector,
    covariance: Covariance6x6,
    interval: Interval,
    force_model: ForceModelHandle,
) -> tuple[Trajectory, list[Covariance6x6]]:
    """Propagate mean state and a time series of covariances (stub contract).

    Purpose:
        Feed conjunction Pc algorithms requiring uncertainty tubes.

    When to use:
        Before ``compute_pc`` or Monte-Carlo screening.

    Prerequisites:
        ``state`` and ``covariance`` share epoch/frame; force model configured.

    Post-checks:
        Verify PSD property preserved per sample (tolerance-based).

    Returns:
        Tuple of mean ``Trajectory`` and parallel covariance samples.

    Raises:
        FrameMismatchError: If metadata is inconsistent.
    """
    raise NotImplementedError
