"""Finite-burn maneuver parameterization (stubs)."""

from __future__ import annotations

from node_api.types.maneuver import FiniteBurn, ManeuverPlan
from node_api.types.satellite import SatelliteState
from node_api.types.state import StateVector


def solve_finite_burn_guidance(
    ego: SatelliteState,
    target_state: StateVector,
) -> ManeuverPlan:
    """Convert an impulsive plan sketch into a finite-burn realization (stub).

    Purpose:
        Bridge impulsive screening outputs to thruster duty cycles.

    When to use:
        After an impulsive ``ManeuverPlan`` is approved but vehicle requires finite burns.

    Prerequisites:
        ``ThrusterModel`` on file for ``ego`` satellite.

    Post-checks:
        ``check_fuel_compliance`` with integrated thrust profile.

    Returns:
        ``ManeuverPlan`` annotated with finite-burn metadata where applicable.

    Raises:
        InfeasibleProblemError: If thrust limits cannot achieve required Δv in window.
    """
    raise NotImplementedError


def parameterize_finite_burn_arc(burn: FiniteBurn, ego: SatelliteState) -> ManeuverPlan:
    """Expand a ``FiniteBurn`` profile into a trajectory-compatible plan shell (stub).

    Purpose:
        Feed low-level GNC with attitude/thrust schedules.

    When to use:
        When solvers emit ``FiniteBurn`` instead of impulsive ``Maneuver``.

    Prerequisites:
        Profiles reference valid GNC tables.

    Post-checks:
        ``check_induced_conjunctions`` along integrated arc.

    Returns:
        ``ManeuverPlan`` placeholder until integrator is implemented.

    Raises:
        InfeasibleProblemError: If attitude profile violates keep-out cones.
    """
    raise NotImplementedError
