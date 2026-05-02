"""Station keeping mission recipes (stubs)."""

from __future__ import annotations

from node_api.types.constellation import HouseRules
from node_api.types.maneuver import ManeuverPlan
from node_api.types.satellite import SatelliteState


def plan_station_keeping(
    ego: SatelliteState,
    house_rules: HouseRules,
) -> ManeuverPlan:
    """Maintain satellite within ``OperationalBox`` tolerances.

    Purpose:
        Routine east/west or radial/in-track trims for GEO slot keeping.

    When to use:
        When predicted elements drift outside ``house_rules.operational_boxes[ego.sat_id]``.

    Prerequisites:
        ``ego`` propagated to evaluation epoch; ``HouseRules`` loaded.

    Post-checks:
        ``check_induced_conjunctions`` and ``check_keep_out_compliance``.

    Returns:
        Small Δv ``ManeuverPlan``.

    Raises:
        InfeasibleProblemError: If deadband cannot be recovered within a single cycle.
    """
    raise NotImplementedError
