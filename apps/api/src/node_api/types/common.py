"""Shared linear-algebra primitives and intervals."""

from __future__ import annotations

from typing import Self

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from node_api.types.time import Epoch


class Vector3(BaseModel):
    """Three-vector stored as a length-3 float64 NumPy array (e.g. km, km/s, or m by context)."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True, extra="forbid")

    data: NDArray[np.float64] = Field(..., description="Shape (3,) float64 vector.")

    @field_validator("data", mode="before")
    @classmethod
    def _coerce_and_validate_shape(cls, v: object) -> NDArray[np.float64]:
        arr = np.asarray(v, dtype=np.float64).reshape(-1)
        if arr.shape != (3,):
            msg = f"Vector3 requires shape (3,), got {arr.shape}"
            raise ValueError(msg)
        return arr


class Matrix3x3(BaseModel):
    """3×3 matrix stored as NumPy array (e.g. rotation DCM)."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True, extra="forbid")

    data: NDArray[np.float64] = Field(..., description="Shape (3, 3) float64 matrix.")

    @field_validator("data", mode="before")
    @classmethod
    def _validate_shape(cls, v: object) -> NDArray[np.float64]:
        arr = np.asarray(v, dtype=np.float64)
        if arr.shape != (3, 3):
            msg = f"Matrix3x3 requires shape (3, 3), got {arr.shape}"
            raise ValueError(msg)
        return arr


class Matrix6x6(BaseModel):
    """6×6 matrix (e.g. Cartesian position-velocity covariance blocks)."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True, extra="forbid")

    data: NDArray[np.float64] = Field(..., description="Shape (6, 6) float64 matrix.")

    @field_validator("data", mode="before")
    @classmethod
    def _validate_shape(cls, v: object) -> NDArray[np.float64]:
        arr = np.asarray(v, dtype=np.float64)
        if arr.shape != (6, 6):
            msg = f"Matrix6x6 requires shape (6, 6), got {arr.shape}"
            raise ValueError(msg)
        return arr


class Interval(BaseModel):
    """Half-open or closed operational window in time; end strictly after start."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: Epoch
    end: Epoch

    @model_validator(mode="after")
    def _validate_ordering(self) -> Self:
        if self.end.as_utc_datetime() <= self.start.as_utc_datetime():
            msg = "Interval.end must be strictly after Interval.start (compared in UTC)."
            raise ValueError(msg)
        return self
