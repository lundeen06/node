"""Collision avoidance optimization primitives (stubs)."""

from __future__ import annotations

from node_api.types.conjunction import CloseApproach
from node_api.types.constellation import HouseRules
from node_api.types.maneuver import ManeuverPlan
from node_api.types.satellite import SatelliteState


def solve_impulsive_avoidance(
    ego: SatelliteState,
    threat: CloseApproach,
    max_delta_v_mps: float,
    pc_target: float,
) -> ManeuverPlan:
    """Generate an optimal evasion maneuver against a specified threat.

    Purpose:
        Computes a single impulsive Δv that reduces probability of collision below threshold,
        given a fixed burn time. Convex when linearized around the current trajectory.

    When to use:
        After confirming a conjunction's Pc exceeds operational threshold (typically 1e-5 for
        uncrewed assets, 1e-4 for crewed). Use as the inner solve inside ``plan_collision_avoidance``,
        which handles burn-time optimization.

    Prerequisites:
        - ``compute_pc`` to confirm the conjunction is real and above threshold
        - ``get_satellite_state`` for the latest ego state and covariance (via ``SatelliteState``)
        - ``get_house_rules`` to load the keep-out box and operator preferences

    Post-checks (always run after this returns):
        - ``check_induced_conjunctions`` on the resulting plan
        - ``check_fuel_compliance`` against current fuel + reserve

    Returns:
        ``ManeuverPlan`` with a single ``Maneuver``, predicted post-state, and Δv cost.

    Raises:
        InfeasibleProblemError: If no Δv within ``max_delta_v_mps`` satisfies the Pc constraint.
    """
    raise NotImplementedError


def solve_optimal_avoidance_timing(
    ego: SatelliteState,
    threat: CloseApproach,
    house_rules: HouseRules,
) -> ManeuverPlan:
    """Search over burn epoch within policy windows to minimize fuel while meeting Pc gates.

    Purpose:
        Outer loop around ``solve_impulsive_avoidance`` for timing flexibility.

    When to use:
        When a single fixed burn epoch is too conservative or infeasible.

    Prerequisites:
        ``HouseRules`` thresholds loaded; ``ego`` covariance current.

    Post-checks:
        Same as ``solve_impulsive_avoidance``.

    Returns:
        ``ManeuverPlan`` with optimized burn timing.

    Raises:
        InfeasibleProblemError: If no feasible epoch exists in the admissible window.
    """
    raise NotImplementedError
