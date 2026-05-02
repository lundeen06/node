"""Hohmann transfer primitives (stubs)."""

from __future__ import annotations

from node_api.types.maneuver import ManeuverPlan
from node_api.types.state import KeplerianElements


def solve_hohmann_transfer(
    initial_orbit: KeplerianElements,
    final_semi_major_axis_km: float,
) -> ManeuverPlan:
    """Plan a two-impulse coplanar Hohmann transfer between circular-ish orbits.

    Purpose:
        Baseline phasing and altitude change maneuvers in LEO/GEO contexts.

    When to use:
        When inclination change is negligible and two-burn elliptic transfer is acceptable.

    Prerequisites:
        Elements at a defined epoch; ``elements_to_state`` if starting from Cartesian.

    Post-checks:
        ``check_induced_conjunctions`` and ``check_fuel_compliance`` on the returned plan.

    Returns:
        ``ManeuverPlan`` with two ``Maneuver`` entries.

    Raises:
        InfeasibleProblemError: If radii violate positivity or transfer geometry is undefined.
    """
    raise NotImplementedError
