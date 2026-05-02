"""IERS Earth orientation parameter ingress (stubs)."""

from __future__ import annotations

from node_api.types.catalog import EOPParams
from node_api.types.time import Epoch


def fetch_eop_series(start: Epoch, end: Epoch) -> list[EOPParams]:
    """Fetch Earth orientation parameters covering [start, end].

    Purpose:
        Support micro-arcsecond frame transforms between ECI and ECEF.

    When to use:
        Before high-fidelity numerical propagation or ground-track prediction.

    Prerequisites:
        ``start`` < ``end`` in a comparable time scale (normalize to UTC ordering).

    Post-checks:
        - Interpolate/extrapolate policy must be chosen by caller (not implemented here).

    Returns:
        Ordered ``EOPParams`` samples.

    Raises:
        DataUnavailableError: If the IERS bulletin cannot be retrieved.
    """
    raise NotImplementedError
