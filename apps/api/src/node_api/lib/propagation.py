"""Layer 2 — trajectory propagation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import NewType

import numpy as np

from node_api.physics_runtime import ensure_physics_importable
from node_api.types.catalog import TLE
from node_api.types.common import Interval, Vector3
from node_api.types.frames import Frame
from node_api.types.state import Covariance6x6, StateVector
from node_api.types.time import Epoch, TimeScale
from node_api.types.trajectory import Trajectory, TrajectorySample

ensure_physics_importable()
from physics.infra.propagate_orbit import propagate_absolute_elements  # noqa: E402
from physics.infra.slate import AbsoluteOrbitalElements  # noqa: E402

from node_api.lib.tle_physics import trajectory_states_sgp4  # noqa: E402

ForceModelHandle = NewType("ForceModelHandle", str)


def _sample_count(duration_s: float) -> int:
    return max(2, min(500, int(duration_s / 60.0) + 1))


def _trajectory_from_pv_columns(
    sat_id: str,
    start_utc: datetime,
    duration_s: float,
    dt_grid: np.ndarray,
    pv: np.ndarray,
) -> Trajectory:
    samples: list[TrajectorySample] = []
    n = pv.shape[1]
    for j in range(n):
        dt_utc = (start_utc + timedelta(seconds=float(dt_grid[j]))).astimezone(UTC)
        pos_km = pv[0:3, j] / 1000.0
        vel_km_s = pv[3:6, j] / 1000.0
        epoch = Epoch(instant=dt_utc, scale=TimeScale.UTC)
        state = StateVector(
            position_km=Vector3(data=np.asarray(pos_km, dtype=np.float64)),
            velocity_km_s=Vector3(data=np.asarray(vel_km_s, dtype=np.float64)),
            epoch=epoch,
            frame=Frame.ECI_J2000,
        )
        samples.append(TrajectorySample(epoch=epoch, state=state))
    return Trajectory(sat_id=sat_id, samples=samples)


def propagate_mean_elements_at_times(
    elements: AbsoluteOrbitalElements,
    ephemeris_epoch_utc: datetime,
    sample_times_utc: list[datetime],
    sat_id: str,
    *,
    use_j2: bool = True,
) -> Trajectory:
    """Evaluate mean-element propagation at explicit UTC sample times."""
    if len(sample_times_utc) < 2:
        msg = "At least two sample times are required."
        raise ValueError(msg)
    ep = ephemeris_epoch_utc.astimezone(UTC)
    offsets = np.array([(t.astimezone(UTC) - ep).total_seconds() for t in sample_times_utc], dtype=np.float64)
    pv = propagate_absolute_elements(elements, offsets, use_j2=use_j2)
    samples: list[TrajectorySample] = []
    for j, t in enumerate(sample_times_utc):
        dt_utc = t.astimezone(UTC)
        pos_km = pv[0:3, j] / 1000.0
        vel_km_s = pv[3:6, j] / 1000.0
        epoch = Epoch(instant=dt_utc, scale=TimeScale.UTC)
        state = StateVector(
            position_km=Vector3(data=np.asarray(pos_km, dtype=np.float64)),
            velocity_km_s=Vector3(data=np.asarray(vel_km_s, dtype=np.float64)),
            epoch=epoch,
            frame=Frame.ECI_J2000,
        )
        samples.append(TrajectorySample(epoch=epoch, state=state))
    return Trajectory(sat_id=sat_id, samples=samples)


def propagate_mean_elements(
    elements: AbsoluteOrbitalElements,
    ephemeris_epoch_utc: datetime,
    interval: Interval,
    sat_id: str,
    *,
    use_j2: bool = True,
) -> Trajectory:
    """Propagate mean classical elements from ``ephemeris_epoch_utc`` using ``propagate_oe`` / ``oe_to_pv``."""
    start = interval.start.as_utc_datetime()
    end = interval.end.as_utc_datetime()
    duration_s = (end - start).total_seconds()
    n = _sample_count(duration_s)
    dt_grid = np.linspace(0.0, duration_s, n)
    times = [start + timedelta(seconds=float(x)) for x in dt_grid]
    return propagate_mean_elements_at_times(elements, ephemeris_epoch_utc, times, sat_id, use_j2=use_j2)


def build_force_model(sat_id: str, include_drag: bool, include_srp: bool) -> ForceModelHandle:
    """Assemble a numerical force model handle for a satellite."""
    raise NotImplementedError


def propagate_tle_sgp4_sample_times(
    line1: str,
    line2: str,
    sample_times_utc: list[datetime],
    sat_id: str,
) -> Trajectory:
    """Dense trajectory from stored TLE lines using **SGP4** at each sample UTC."""
    if len(sample_times_utc) < 2:
        msg = "At least two sample times are required."
        raise ValueError(msg)
    states = trajectory_states_sgp4(line1, line2, sample_times_utc)
    samples: list[TrajectorySample] = []
    for t, r_km, v_km_s in states:
        epoch = Epoch(instant=t, scale=TimeScale.UTC)
        state = StateVector(
            position_km=Vector3(data=np.asarray(r_km, dtype=np.float64)),
            velocity_km_s=Vector3(data=np.asarray(v_km_s, dtype=np.float64)),
            epoch=epoch,
            frame=Frame.ECI_J2000,
        )
        samples.append(TrajectorySample(epoch=epoch, state=state))
    return Trajectory(sat_id=sat_id, samples=samples)


def propagate_sgp4(tle: TLE, interval: Interval, *, use_j2: bool = True) -> Trajectory:
    """Propagate a TLE using **SGP4** at each sample time (standard NORAD model).

    ``use_j2`` is ignored; Kept for API compatibility. SGP4 already includes secular drag/J2 effects
    appropriate for two-line element sets.
    """
    del use_j2
    start = interval.start.as_utc_datetime()
    end = interval.end.as_utc_datetime()
    duration_s = (end - start).total_seconds()
    n = _sample_count(duration_s)
    dt_grid = np.linspace(0.0, duration_s, n)
    times = [start + timedelta(seconds=float(x)) for x in dt_grid]
    return propagate_tle_sgp4_sample_times(tle.line1, tle.line2, times, str(tle.satellite_number))


def propagate_numerical(
    state: StateVector,
    interval: Interval,
    force_model: ForceModelHandle,
) -> Trajectory:
    """High-fidelity numerical propagation with a configured force model."""
    raise NotImplementedError


def propagate_with_uncertainty(
    state: StateVector,
    covariance: Covariance6x6,
    interval: Interval,
    force_model: ForceModelHandle,
) -> tuple[Trajectory, list[Covariance6x6]]:
    """Propagate mean state and a time series of covariances (stub contract)."""
    raise NotImplementedError
