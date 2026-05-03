"""``enum.StrEnum`` is Python 3.11+; provide equivalent on 3.10 for local development."""

from __future__ import annotations

try:
    from enum import StrEnum as StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[misc]
        """String-valued enum (minimal subset of :class:`enum.StrEnum`)."""
