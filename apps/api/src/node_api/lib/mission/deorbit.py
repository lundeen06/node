"""Deorbit and disposal mission recipes (stubs)."""

from __future__ import annotations

from node_api.types.maneuver import ManeuverPlan
from node_api.types.satellite import SatelliteState


def plan_disposal_sequence(ego: SatelliteState, target_perigee_km: float) -> ManeuverPlan:
    """Plan a controlled lowering toward a target perigee / reentry corridor (stub).

    Purpose:
        Post-mission disposal complying with IADC-style guidelines.

    When to use:
        When satellite reaches end-of-life and must be passivated/deorbited.

    Prerequisites:
        Mass and drag properties current; ground tracking for confirmation.

    Post-checks:
        ``check_induced_conjunctions`` during low passes; ``check_keep_out_compliance``.

    Returns:
        ``ManeuverPlan`` with one or more retrograde burns.

    Raises:
        InfeasibleProblemError: If insufficient fuel to meet corridor constraints.
    """
    raise NotImplementedError
