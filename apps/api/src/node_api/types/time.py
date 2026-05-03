"""Time scales and tagged instants — no naive datetimes in the domain layer."""

from __future__ import annotations

from datetime import UTC, datetime
from node_api.compat_enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TimeScale(StrEnum):
    """Physical or civil time scale for an instant."""

    UTC = "UTC"
    UT1 = "UT1"
    TAI = "TAI"
    TT = "TT"
    GPS = "GPS"


class Epoch(BaseModel):
    """A single instant with an explicit time scale.

    All domain logic that orders events (conjunction TCA, maneuver epochs) should
    carry ``Epoch`` rather than bare ``datetime`` values so conversions between scales
    are deliberate at frame/transform boundaries.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    instant: datetime = Field(
        ...,
        description="Timezone-aware instant; interpret using ``scale``.",
    )
    scale: TimeScale = Field(
        ...,
        description="Declared scale of ``instant`` before operational normalization.",
    )

    @field_validator("instant")
    @classmethod
    def _reject_naive(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            msg = "Epoch.instant must be timezone-aware (use UTC or an explicit offset)."
            raise ValueError(msg)
        return v

    def as_utc_datetime(self) -> datetime:
        """Return the instant converted to UTC for ordering and comparisons."""
        return self.instant.astimezone(UTC)
