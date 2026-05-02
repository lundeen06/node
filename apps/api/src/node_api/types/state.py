"""Orbital state representations: Cartesian, covariance, classical and equinoctial elements."""

from __future__ import annotations

from typing import Self

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, model_validator

from node_api.types.common import Matrix6x6, Vector3
from node_api.types.frames import Frame
from node_api.types.time import Epoch


class StateVector(BaseModel):
    """Cartesian position and velocity at an epoch in an explicit frame.

    The ``frame`` field is part of the type identity: a vector tagged ``ECEF_ITRF`` is
    not interchangeable with one tagged ``ECI_J2000`` without passing through ``convert_frame``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    position_km: Vector3 = Field(..., description="Position in km.")
    velocity_km_s: Vector3 = Field(..., description="Velocity in km/s.")
    epoch: Epoch
    frame: Frame


class Covariance6x6(BaseModel):
    """6×6 position-velocity covariance with the same epoch/frame metadata as the mean state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    matrix: Matrix6x6
    epoch: Epoch
    frame: Frame

    @model_validator(mode="after")
    def _symmetric_psd_hint(self) -> Self:
        m = self.matrix.data
        arr = np.asarray(m.data, dtype=np.float64)
        if not _is_symmetric(arr):
            msg = "Covariance6x6.matrix must be symmetric."
            raise ValueError(msg)
        if not _is_positive_semidefinite(arr):
            msg = "Covariance6x6.matrix must be positive semi-definite."
            raise ValueError(msg)
        return self


def _is_symmetric(arr: NDArray[np.float64], tol: float = 1e-9) -> bool:
    return bool(np.allclose(arr, arr.T, atol=tol))


def _is_positive_semidefinite(arr: NDArray[np.float64], tol: float = -1e-8) -> bool:
    sym = (arr + arr.T) / 2.0
    eig = np.linalg.eigvalsh(sym)
    return bool(np.all(eig >= tol))


class KeplerianElements(BaseModel):
    """Classical orbital elements in radians and km.

    .. warning::
        This parameterization is **singular** for near-circular orbits (``e → 0``) and
        near-equatorial orbits (``i → 0``). Prefer :class:`EquinoctialElements` for filters,
        differential corrections, or optimization when those degeneracies appear.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    semi_major_axis_km: float = Field(..., gt=0, description="Semi-major axis a (km).")
    eccentricity: float = Field(..., ge=0, lt=1, description="Eccentricity e (elliptic).")
    inclination_rad: float = Field(..., ge=0, description="Inclination i (rad).")
    raan_rad: float = Field(..., description="Right ascension of ascending node Ω (rad).")
    arg_perigee_rad: float = Field(..., description="Argument of periapsis ω (rad).")
    true_anomaly_rad: float | None = Field(
        default=None,
        description="True anomaly ν (rad). Provide this **or** ``mean_anomaly_rad``.",
    )
    mean_anomaly_rad: float | None = Field(
        default=None,
        description="Mean anomaly M (rad). Provide this **or** ``true_anomaly_rad``.",
    )

    @model_validator(mode="after")
    def _one_anomaly(self) -> Self:
        if (self.true_anomaly_rad is None) == (self.mean_anomaly_rad is None):
            msg = "Exactly one of true_anomaly_rad or mean_anomaly_rad must be set."
            raise ValueError(msg)
        return self


class EquinoctialElements(BaseModel):
    """Modified equinoctial elements — nonsingular for e≈0 and i≈0."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semi_parameter_km: float = Field(..., gt=0, description="Semi-parameter p (km).")
    f: float = Field(..., description="Component f = e sin(Ω + ω).")
    g: float = Field(..., description="Component g = e cos(Ω + ω).")
    h: float = Field(..., description="Component h = tan(i/2) sin Ω.")
    k: float = Field(..., description="Component k = tan(i/2) cos Ω.")
    mean_longitude_rad: float = Field(..., description="Mean longitude L = Ω + ω + M (rad).")

