"""Layer 7 — post-solve validation gates (stubs)."""

from __future__ import annotations

from node_api.types.catalog import CatalogObject
from node_api.types.constellation import HouseRules
from node_api.types.maneuver import ManeuverPlan, ValidationOutcome
from node_api.types.satellite import SatelliteState


def check_induced_conjunctions(
    plan: ManeuverPlan,
    catalog: list[CatalogObject],
) -> list[ValidationOutcome]:
    """Screen a maneuver plan's predicted ephemeris for new conjunction risks.

    Purpose:
        Ensure mitigation does not create a worse secondary risk.

    When to use:
        **Always** after solvers return a ``ManeuverPlan``.

    Prerequisites:
        ``propagate_numerical`` or equivalent arc for post-burn states.

    Post-checks:
        If failures occur, call avoidance again with tightened windows.

    Returns:
        List of ``ValidationOutcome`` entries (non-empty on failure).

    Raises:
        DataUnavailableError: If catalog snapshot missing.
    """
    raise NotImplementedError


def check_keep_out_compliance(plan: ManeuverPlan, house_rules: HouseRules) -> list[ValidationOutcome]:
    """Verify predicted trajectory respects volumetric and geographic keep-outs.

    Purpose:
        Policy enforcement beyond conjunction risk.

    When to use:
        After ``check_geometric_keep_out``-style checks at discrete samples are integrated.

    Prerequisites:
        ``house_rules.keep_out_zones`` populated.

    Post-checks:
        Operator must reject or re-solve if any entry ``passed is False``.

    Returns:
        ``ValidationOutcome`` list.

    Raises:
        FrameMismatchError: If zone frames cannot be aligned.
    """
    raise NotImplementedError


def check_fuel_compliance(plan: ManeuverPlan, ego: SatelliteState, reserve_kg: float) -> ValidationOutcome:
    """Ensure maneuver fuel cost leaves at least ``reserve_kg`` margin.

    Purpose:
        Hard safety gate on consumables.

    When to use:
        After any plan touches thrusters.

    Prerequisites:
        ``ego.fuel_kg`` current; ``plan.total_fuel_kg`` computed consistently.

    Post-checks:
        None beyond operator acknowledgement.

    Returns:
        Single ``ValidationOutcome``.

    Raises:
        InfeasibleProblemError: If reserve cannot be met (optional policy—may return failed outcome).
    """
    raise NotImplementedError


def check_operational_box_compliance(plan: ManeuverPlan, house_rules: HouseRules) -> list[ValidationOutcome]:
    """Verify post-maneuver elements remain within per-satellite operational boxes.

    Purpose:
        GEO slot or constellation slot keeping without manual element review.

    When to use:
        After station-keeping or phasing plans.

    Prerequisites:
        ``house_rules.operational_boxes`` contains ``plan.sat_id``.

    Post-checks:
        Escalate to mission planner if tolerances will be exceeded next cycle.

    Returns:
        ``ValidationOutcome`` list.

    Raises:
        DataUnavailableError: If no operational box is configured for the asset.
    """
    raise NotImplementedError
