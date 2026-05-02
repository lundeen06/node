"""Collision avoidance mission recipes (stubs)."""

from __future__ import annotations

from node_api.types.conjunction import Conjunction
from node_api.types.constellation import HouseRules
from node_api.types.maneuver import ManeuverPlan
from node_api.types.satellite import SatelliteState


def plan_collision_avoidance(
    ego: SatelliteState,
    event: Conjunction,
    house_rules: HouseRules,
) -> ManeuverPlan:
    """Orchestrate screening, timing search, and impulsive avoidance for a conjunction.

    Purpose:
        End-to-end mitigation planning with policy thresholds from ``HouseRules``.

    When to use:
        After internal screening or CDM ingestion flags ``event.status == NEW``.

    Prerequisites:
        ``compute_pc`` already reflected in ``event``; covariance current in ``ego``.

    Post-checks:
        ``check_induced_conjunctions``, ``check_keep_out_compliance``, ``check_fuel_compliance``.

    Returns:
        Executable ``ManeuverPlan`` pending operator approval.

    Raises:
        InfeasibleProblemError: If mitigation is impossible within fuel/thrust limits.
    """
    raise NotImplementedError
