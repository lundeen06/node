"""Layer 9 — gated side effects (stubs; every entrypoint requires ``ApprovalRecord``)."""

from __future__ import annotations

from node_api.types.approval import ApprovalRecord, AuditEntry, OperatorDecision
from node_api.types.conjunction import CDMResponse
from node_api.types.ground import ContactRequest
from node_api.types.maneuver import ManeuverId, ManeuverPlan


def queue_maneuver(plan: ManeuverPlan, approval: ApprovalRecord) -> ManeuverId:
    """Enqueue an approved maneuver plan for execution on the flight dynamics stack.

    Purpose:
        Transition from planning to command generation / uplink scheduling.

    When to use:
        Only after operator review and ``ApprovalRecord`` issuance for ``plan``.

    Prerequisites:
        ``plan.validation_results`` all pass; ``approval.plan_id`` matches ``plan`` identifier policy.

    Post-checks:
        Monitor execution telemetry; append audit entries on completion.

    Returns:
        Opaque ``ManeuverId`` for tracking.

    Raises:
        NodeLibraryError: If approval is stale or plan is locked.
    """
    raise NotImplementedError


def schedule_uplink(request: ContactRequest, approval: ApprovalRecord) -> str:
    """Reserve a ground contact per ``ContactRequest`` after human approval.

    Purpose:
        Bind RF assets to approved contact windows.

    When to use:
        After maneuver or payload operations require downlink/uplink.

    Prerequisites:
        ``find_ground_passes`` confirms feasibility; ``approval`` references same plan/window policy.

    Post-checks:
        Confirm station scheduler acknowledges the reservation id.

    Returns:
        Provider-specific schedule identifier string.

    Raises:
        NodeLibraryError: If the window conflicts with another approved reservation.
    """
    raise NotImplementedError


def acknowledge_cdm(cdm_id: str, approval: ApprovalRecord, note: str | None = None) -> CDMResponse:
    """Record formal acknowledgement of a CDM for regulatory and internal workflow tracking.

    Purpose:
        Close the loop on conjunction messages with traceable accountability.

    When to use:
        After operators review CDM contents, even if no maneuver is executed.

    Prerequisites:
        ``approval.operator_id`` matches authenticated principal; ``cdm_id`` valid.

    Post-checks:
        Update conjunction workflow status to ``ACKNOWLEDGED`` in persistence layer.

    Returns:
        ``CDMResponse`` echoing acknowledgement metadata.

    Raises:
        NodeLibraryError: If CDM already acknowledged under conflicting policy.
    """
    raise NotImplementedError


def log_decision(decision: OperatorDecision, approval: ApprovalRecord) -> AuditEntry:
    """Append an immutable audit row coupling an operator decision with approval metadata.

    Purpose:
        Forensic traceability for agent suggestions vs human overrides.

    When to use:
        Whenever ``OperatorDecision`` is finalized (approve/reject/edit/escalate).

    Prerequisites:
        ``approval.plan_id`` aligns with ``decision.plan_id`` per policy.

    Post-checks:
        Verify append-only store accepted the hash chain predecessor (future).

    Returns:
        Persisted ``AuditEntry`` snapshot.

    Raises:
        NodeLibraryError: If duplicate logging or tamper checks fail.
    """
    raise NotImplementedError
