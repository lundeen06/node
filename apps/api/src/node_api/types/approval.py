"""Human accountability artifacts for gated actions and audit logging."""

from __future__ import annotations

from node_api.compat_enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from node_api.types.time import Epoch


class AuthMethod(StrEnum):
    """How the approving principal authenticated."""

    SSO = "SSO"
    MFA = "MFA"
    WORKFLOW_POLICY = "WORKFLOW_POLICY"


class OperatorDecisionKind(StrEnum):
    """Operator disposition on a proposed plan."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    EDIT = "EDIT"
    ESCALATE = "ESCALATE"


class ApprovalRecord(BaseModel):
    """Non-forgeable (operationally) proof that a plan was cleared for execution.

    **Required** on every Layer-9 ``actions`` library call so automation cannot bypass
    accountability boundaries.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    operator_id: str
    approved_at: Epoch
    plan_id: str
    edits_applied: list[str] = Field(
        default_factory=list,
        description="Human-readable list of parameter edits applied before approval.",
    )
    authentication_method: AuthMethod
    policy_id: str | None = Field(
        default=None,
        description="If approved under automated policy, reference that policy version.",
    )


class OperatorDecision(BaseModel):
    """Structured operator response to a proposed maneuver or workflow output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operator_id: str
    decision: OperatorDecisionKind
    plan_id: str
    timestamp: Epoch
    edits: list[str] | None = None
    rejection_reason: str | None = None


class AuditEntry(BaseModel):
    """Append-only audit row for agents, operators, and actuators."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    timestamp: Epoch
    actor_id: str
    actor_type: str = Field(..., description="AGENT | OPERATOR | SYSTEM")
    action: str
    payload_summary: str
    correlation_id: str | None = None
