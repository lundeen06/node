"""Smoke: every module import resolves."""

from __future__ import annotations


def test_import_package() -> None:
    import node_api  # noqa: F401


def test_import_main() -> None:
    from node_api import main  # noqa: F401


def test_import_types_submodules() -> None:
    from node_api.types import (  # noqa: F401
        approval,
        catalog,
        common,
        conjunction,
        constellation,
        frames,
        ground,
        maneuver,
        satellite,
        state,
        time,
        trajectory,
        workflow,
    )


def test_import_lib_layers() -> None:
    from node_api.lib import (  # noqa: F401
        actions,
        constellation,
        environment,
        frames,
        propagation,
        validation,
    )
    from node_api.lib.ingress import celestrak, constellation_presets, eop, space_track, space_weather  # noqa: F401
    from node_api.lib.mission import (  # noqa: F401
        circular_altitude_transfer,
        collision_avoidance,
        deorbit,
        phasing,
        plane_change,
        replenishment,
        station_keeping,
    )
    from node_api.lib.solvers import (  # noqa: F401
        avoidance,
        finite_burn,
        hohmann,
        lambert,
        low_thrust,
    )


def test_import_routes() -> None:
    from node_api.routes import agent, conjunctions, maneuvers, satellites, spacecraft  # noqa: F401


def test_import_db() -> None:
    from node_api.db import models, session  # noqa: F401
