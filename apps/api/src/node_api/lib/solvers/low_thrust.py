"""Low-thrust / continuous thrust planning (stubs)."""

from __future__ import annotations

from node_api.types.common import Interval
from node_api.types.maneuver import ContinuousManeuver, ManeuverPlan
from node_api.types.satellite import SatelliteState
from node_api.types.state import StateVector


def solve_low_thrust_transfer(
    ego: SatelliteState,
    target: StateVector,
    interval: Interval,
) -> ManeuverPlan:
    """Plan a continuous-thrust arc between boundary states (stub).

    Purpose:
        Electric propulsion orbit raising or spiral transfers.

    When to use:
        When ``ThrusterModel.kind == ELECTRIC`` and flight time is flexible.

    Prerequisites:
        ``interval`` covers allowable thrust windows; ``propagate_numerical`` for validation arcs.

    Post-checks:
        ``check_induced_conjunctions`` along dense samples.

    Returns:
        ``ManeuverPlan`` embedding a ``ContinuousManeuver`` reference.

    Raises:
        InfeasibleProblemError: If thrust-to-mass cannot close the gap in ``interval``.
    """
    raise NotImplementedError


def expand_continuous_maneuver(maneuver: ContinuousManeuver) -> ManeuverPlan:
    """Discretize a continuous maneuver for validation and conjunction screening (stub).

    Purpose:
        Produce a dense ephemeris for Layer-7 checks.

    When to use:
        After ``solve_low_thrust_transfer`` returns a continuous profile.

    Prerequisites:
        Thrust/attitude profiles resolvable to body rates.

    Post-checks:
        ``check_keep_out_compliance`` on discretized samples.

    Returns:
        ``ManeuverPlan`` with many short impulsive segments as a stand-in.

    Raises:
        InfeasibleProblemError: If discretization violates minimum step policy.
    """
    raise NotImplementedError
