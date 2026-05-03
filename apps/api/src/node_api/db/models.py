"""ORM models for persisted spacecraft catalog data."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SpacecraftRow(Base):
    """Latest Space-Track GP snapshot and derived mean classical elements per asset."""

    __tablename__ = "spacecraft"

    sat_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    norad_catalog_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    purpose: Mapped[str] = mapped_column(Text, default="")
    gp_snapshot_json: Mapped[str] = mapped_column(Text)
    tle_line1: Mapped[str] = mapped_column(Text)
    tle_line2: Mapped[str] = mapped_column(Text)
    oe_vector_json: Mapped[str] = mapped_column(Text)
    ephemeris_epoch_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
