"""Collision avoidance mission recipes — Lambert-backed impulsive planning."""

from __future__ import annotations

from node_api.lib.solvers.avoidance import solve_optimal_avoidance_timing
from node_api.types.conjunction import CloseApproach, Conjunction
from node_api.types.constellation import HouseRules
from node_api.types.maneuver import ManeuverPlan
from node_api.types.satellite import SatelliteState


def _close_approach_from_conjunction(event: Conjunction) -> CloseApproach:
    return CloseApproach(
        id=event.id,
        primary_id=event.primary_id,
        secondary_id=event.secondary_id,
        tca=event.tca,
        miss_distance_km=event.miss_distance_km,
        relative_velocity_km_s=event.relative_velocity_km_s,
        source=event.source,
        created_at=event.created_at,
    )


def plan_collision_avoidance(
    ego: SatelliteState,
    event: Conjunction,
    house_rules: HouseRules,
    *,
    tle_line1: str | None = None,
    tle_line2: str | None = None,
) -> ManeuverPlan:
    """Build a Lambert single-impulse avoidance plan bounded by ``HouseRules.max_auto_delta_v_mps``.

    Maps ``event`` to a :class:`CloseApproach` for :func:`solve_optimal_avoidance_timing` (several
    pre-TCA burn leads, minimum total Δv) and uses ``house_rules.pc_mitigation_threshold`` as the Pc
    policy gate in metadata (post-maneuver Pc is not recomputed in this version).

    When ``tle_line1`` / ``tle_line2`` are set, the Lambert departure state is **SGP4 at the burn epoch**
    (otherwise the caller's ``ego`` PV is reused with only the epoch shifted — legacy behavior).
    """
    threat = _close_approach_from_conjunction(event)
    return solve_optimal_avoidance_timing(
        ego,
        threat,
        house_rules,
        tle_line1=tle_line1,
        tle_line2=tle_line2,
    )
