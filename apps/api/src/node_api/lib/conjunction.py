"""Layer 3 — conjunction screening and Pc (stubs)."""

from __future__ import annotations

from node_api.types.catalog import CatalogObject
from node_api.types.common import Interval
from node_api.types.conjunction import CloseApproach, PcMethod
from node_api.types.state import Covariance6x6, StateVector

PcEstimate = tuple[float, PcMethod]


def find_close_approach(
    primary: StateVector,
    secondary: StateVector,
    search_interval: Interval,
) -> CloseApproach:
    """Find geometric closest approach between two states over a search window.

    Purpose:
        Produce a ``CloseApproach`` for subsequent Pc evaluation or operator review.

    When to use:
        When you have two Cartesian states and need a TCA/miss distance without Pc yet.

    Prerequisites:
        States converted to a common frame via ``convert_frame``.

    Post-checks:
        Always run ``compute_pc`` if decisioning depends on probability, not geometry alone.

    Returns:
        ``CloseApproach`` with TCA and relative speed populated.

    Raises:
        FrameMismatchError: If epoch/frame alignment is invalid.
    """
    raise NotImplementedError


def compute_pc(
    approach: CloseApproach,
    primary_cov: Covariance6x6,
    secondary_cov: Covariance6x6,
    method: PcMethod,
) -> PcEstimate:
    """Compute collision probability for a close approach.

    Purpose:
        Quantify risk given relative geometry and uncertainty.

    When to use:
        After ``find_close_approach`` or when ingesting CDM geometry.

    Prerequisites:
        Covariance objects compatible with ``method`` (typed as object until wired).

    Post-checks:
        Compare against ``HouseRules.pc_mitigation_threshold``; if exceeded, call solvers.

    Returns:
        Tuple of ``(pc, method)`` for traceability.

    Raises:
        DataUnavailableError: If required covariance blocks are missing.
    """
    raise NotImplementedError


def screen_catalog_against_ego(
    ego: StateVector,
    catalog: list[CatalogObject],
    horizon: Interval,
) -> list[CloseApproach]:
    """Screen many catalog objects against a single ego state.

    Purpose:
        Constellation-wide situational awareness from a propagated ego arc.

    When to use:
        On a schedule or after state updates for active satellites.

    Prerequisites:
        ``ego`` propagated across ``horizon`` internally or expanded by caller policy.

    Post-checks:
        Promote interesting hits to ``compute_pc`` and operator queues.

    Returns:
        Sorted list of ``CloseApproach`` (may be empty).

    Raises:
        FrameMismatchError: If catalog states are not aligned to ego frame.
    """
    raise NotImplementedError


def screen_constellation(
    states: dict[str, StateVector],
    catalog: list[CatalogObject],
    horizon: Interval,
) -> list[CloseApproach]:
    """Pairwise-expand screening across multiple ego satellites.

    Purpose:
        Fleet-level conjunction screening in one batch call.

    When to use:
        When operating more than one asset under shared catalog data.

    Prerequisites:
        All ``states`` mapped to comparable frames and epochs per internal policy.

    Post-checks:
        De-duplicate approaches involving the same secondary NORAD id.

    Returns:
        Combined ``CloseApproach`` list tagged by primary id in future extension.

    Raises:
        FrameMismatchError: If any member state is inconsistent.
    """
    raise NotImplementedError
