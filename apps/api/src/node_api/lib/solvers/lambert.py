"""Lambert two-point boundary value solver (stubs)."""

from __future__ import annotations

from node_api.types.common import Vector3
from node_api.types.maneuver import ManeuverPlan
from node_api.types.state import StateVector
from node_api.types.time import Epoch


def solve_lambert_problem(
    departure: StateVector,
    arrival_position_km: Vector3,
    arrival_epoch: Epoch,
    prograde: bool,
) -> ManeuverPlan:
    """Solve a two-body Lambert arc between a departure state and a target position/time.

    Purpose:
        Intercept, rendezvous phasing, and some collision-avoidance timing searches.

    When to use:
        When terminal constraints are fixed in inertial space and two-body approx holds.

    Prerequisites:
        ``departure`` and ``arrival_position_km`` expressed in a consistent inertial frame.

    Post-checks:
        ``check_induced_conjunctions`` and ``check_keep_out_compliance``.

    Returns:
        ``ManeuverPlan`` with one or two impulses depending on formulation.

    Raises:
        InfeasibleProblemError: If no conic solution exists for the given TOF.
    """
    raise NotImplementedError
