"""Reference frames and geodetic coordinates."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Frame(StrEnum):
    """Coordinate frame tag carried on states and covariances."""

    ECI_J2000 = "ECI_J2000"
    ECI_GCRF = "ECI_GCRF"
    ECI_TEME = "ECI_TEME"
    ECEF_ITRF = "ECEF_ITRF"
    RIC = "RIC"
    VNB = "VNB"
    LVLH = "LVLH"
    TOPOCENTRIC = "TOPOCENTRIC"


class GeodeticPosition(BaseModel):
    """Latitude / longitude / height above reference ellipsoid."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    latitude_rad: float = Field(..., description="Geodetic latitude, radians, WGS84 unless noted.")
    longitude_rad: float = Field(..., description="Geodetic longitude, radians, east positive.")
    altitude_m: float = Field(..., description="Height above ellipsoid in meters.")
    ellipsoid: str = Field(
        default="WGS84",
        description="Ellipsoid name for operational consistency (default WGS84).",
    )
