"""SGP4 + impulsive Δv coast preview (J2=0 mean elements between burns)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy as np

from node_api.errors import DataUnavailableError
from node_api.lib.tle_physics import trajectory_states_sgp4
from node_api.physics_runtime import ensure_physics_importable

ensure_physics_importable()
from physics.propulsion import util_dyn  # noqa: E402

_MU = float(util_dyn.mu_E)


def _sgp4_pv_km(line1: str, line2: str, when_utc: datetime) -> tuple[np.ndarray, np.ndarray]:
    states = trajectory_states_sgp4(line1, line2, [when_utc.astimezone(UTC)])
    if not states:
        msg = "SGP4 returned no state."
        raise DataUnavailableError(msg)
    _, r_km, v_km_s = states[0]
    return np.asarray(r_km, dtype=np.float64), np.asarray(v_km_s, dtype=np.float64)


def trajectory_preview_maneuvers_m(
    line1: str,
    line2: str,
    times_utc: list[datetime],
    maneuvers: list[tuple[datetime, np.ndarray]],
) -> list[tuple[datetime, np.ndarray, np.ndarray]]:
    """Return ``(t, r_eci_m, v_eci_m_s)`` per sample: SGP4 before first burn, then J2=0 Kepler coast with impulses."""
    if len(times_utc) < 2:
        msg = "At least two sample times are required."
        raise ValueError(msg)
    times_sorted = sorted({t.astimezone(UTC) for t in times_utc})
    burns = sorted(
        ((tb.astimezone(UTC), np.asarray(dv, dtype=np.float64).reshape(3)) for tb, dv in maneuvers),
        key=lambda x: x[0],
    )

    burn_i = 0
    oe_carry: np.ndarray | None = None
    anchor: datetime | None = None
    out: list[tuple[datetime, np.ndarray, np.ndarray]] = []

    for t in times_sorted:
        while burn_i < len(burns) and burns[burn_i][0] <= t:
            tb = burns[burn_i][0]
            if oe_carry is None:
                r_km, v_km_s = _sgp4_pv_km(line1, line2, tb)
                r_m = r_km * 1000.0
                v_mps = v_km_s * 1000.0
            else:
                assert anchor is not None
                dtb = (tb - anchor).total_seconds()
                oe_b = util_dyn.propagate_oe(oe_carry, dtb, mu=_MU, J2=0.0)
                pvb = np.asarray(util_dyn.oe_to_pv(oe_b, _MU), dtype=np.float64).reshape(6)
                r_m, v_mps = pvb[0:3], pvb[3:6]
            v_mps = v_mps + burns[burn_i][1]
            pv = np.concatenate([r_m, v_mps])
            oe_carry = np.asarray(util_dyn.pv_to_oe(pv, _MU), dtype=np.float64)
            anchor = tb
            burn_i += 1

        if oe_carry is None:
            r_km, v_km_s = _sgp4_pv_km(line1, line2, t)
            pos_m = r_km * 1000.0
            vel_mps = v_km_s * 1000.0
        else:
            assert anchor is not None
            dt = (t - anchor).total_seconds()
            oe1 = util_dyn.propagate_oe(oe_carry, dt, mu=_MU, J2=0.0)
            pvb = np.asarray(util_dyn.oe_to_pv(oe1, _MU), dtype=np.float64).reshape(6)
            pos_m, vel_mps = pvb[0:3], pvb[3:6]
        out.append((t, pos_m, vel_mps))
    return out


def maneuvers_from_plan_wire(plan: dict[str, Any]) -> list[tuple[datetime, np.ndarray]]:
    """Parse agent / API ``plan``-shaped dict into (epoch_utc, dv_eci_mps)."""
    out: list[tuple[datetime, np.ndarray]] = []
    for m in plan.get("maneuvers", []):
        if str(m.get("frame", "ECI")).upper() != "ECI":
            msg = "Preview supports ECI-frame maneuvers only."
            raise ValueError(msg)
        inst = datetime.fromisoformat(str(m["epoch_utc"]).replace("Z", "+00:00")).astimezone(UTC)
        dv = m["delta_v_mps"]
        arr = np.array([float(dv["x"]), float(dv["y"]), float(dv["z"])], dtype=np.float64)
        out.append((inst, arr))
    return sorted(out, key=lambda x: x[0])
