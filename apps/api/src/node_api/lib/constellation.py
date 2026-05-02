"""Layer 8 — multi-satellite coordination (stubs)."""

from __future__ import annotations

from node_api.types.common import Interval
from node_api.types.conjunction import Conjunction
from node_api.types.constellation import ConstellationConfig, HouseRules
from node_api.types.maneuver import ManeuverPlan
from node_api.types.satellite import SatelliteState


def solve_constellation_phasing(
    config: ConstellationConfig,
    states: dict[str, SatelliteState],
    house_rules: HouseRules,
) -> dict[str, ManeuverPlan]:
    """Compute coordinated phasing burns across multiple members.

    Purpose:
        Restore slot spacing after drift or deployment.

    When to use:
        When more than one satellite must move without violating mutual safety.

    Prerequisites:
        ``states`` keys cover ``config.member_sat_ids``.

    Post-checks:
        Per-satellite ``check_induced_conjunctions`` against updated fleet ephemerides.

    Returns:
        Map ``sat_id`` → ``ManeuverPlan``.

    Raises:
        InfeasibleProblemError: If collective constraints cannot be satisfied simultaneously.
    """
    raise NotImplementedError


def solve_collective_avoidance(
    threats: list[Conjunction],
    states: dict[str, SatelliteState],
    house_rules: HouseRules,
) -> dict[str, ManeuverPlan]:
    """Jointly optimize avoidance maneuvers for multiple primaries sharing catalog threats.

    Purpose:
        Prevent conflicting maneuvers that trade risk between fleet members.

    When to use:
        When several assets share the same high-risk secondary.

    Prerequisites:
        ``threats`` includes all conjunctions requiring coordinated mitigation.

    Post-checks:
        ``check_induced_conjunctions`` for each plan plus cross-fleet de-confliction.

    Returns:
        Map ``sat_id`` → ``ManeuverPlan``.

    Raises:
        InfeasibleProblemError: If fuel budgets cannot jointly satisfy Pc thresholds.
    """
    raise NotImplementedError


def evaluate_constellation_metrics(
    config: ConstellationConfig,
    states: dict[str, SatelliteState],
    horizon: Interval,
) -> dict[str, float]:
    """Return scalar health metrics per satellite (stub placeholder).

    Purpose:
        Dashboards for spacing, fuel, and risk indices.

    When to use:
        During recurring ops reviews.

    Prerequisites:
        ``states`` propagated through ``horizon``.

    Post-checks:
        None intrinsic.

    Returns:
        ``sat_id`` → metric value map (meaning defined by implementation).

    Raises:
        DataUnavailableError: If any member state is missing.
    """
    raise NotImplementedError
