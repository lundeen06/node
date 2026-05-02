"""Workflow graph model for automation (data layer; no visual blueprint editor in v1)."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkflowLiteralInput(BaseModel):
    """Concrete literal bound to a node input port."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["literal"] = "literal"
    value: float | int | str | bool | None = None


class WorkflowRefInput(BaseModel):
    """Wire from another node's output field, e.g. ``node_a.post_state``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["ref"] = "ref"
    ref: str = Field(
        ...,
        description="Upstream reference ``<node_id>.<output_field>`` per engine convention.",
    )


WorkflowInputBinding = Annotated[
    WorkflowLiteralInput | WorkflowRefInput,
    Field(discriminator="kind"),
]


class WorkflowNode(BaseModel):
    """Single callable step in a workflow DAG."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    function_ref: str = Field(
        ...,
        description='Library path, e.g. "node_api.lib.solvers.avoidance.solve_impulsive_avoidance".',
    )
    inputs: dict[str, WorkflowInputBinding]
    position: tuple[float, float] = Field(
        ...,
        description="Canvas coordinates (px) if a UI exists; ignored by headless runners.",
    )


class WorkflowEdge(BaseModel):
    """Directed data dependency between node ports."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    from_node: str
    from_output: str
    to_node: str
    to_input: str


class ExecutionPolicy(BaseModel):
    """Gates for autonomous vs human-in-the-loop execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    auto_execute_below_dv_mps: float = Field(..., ge=0)
    require_approval_above_dv_mps: float = Field(..., ge=0)
    forbidden_targets: list[str] = Field(
        default_factory=list,
        description="Glob patterns for protected sat_ids (crewed assets, etc.).",
    )

    @model_validator(mode="after")
    def _ordered_thresholds(self) -> Self:
        if self.require_approval_above_dv_mps < self.auto_execute_below_dv_mps:
            msg = "require_approval_above_dv_mps must be >= auto_execute_below_dv_mps."
            raise ValueError(msg)
        return self


class WorkflowGraph(BaseModel):
    """Versioned automation graph referencing library functions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    nodes: list[WorkflowNode] = Field(..., min_length=1)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    schedule_cron: str | None = Field(
        default=None,
        description="Optional cron expression for periodic execution.",
    )
    execution_policy: ExecutionPolicy


class CanvasViewport(BaseModel):
    """Optional 2D pan/zoom state for any future workflow UI."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    offset: tuple[float, float] = (0.0, 0.0)
    scale: float = Field(default=1.0, gt=0)


class WorkflowBundle(BaseModel):
    """Graph plus lightweight presentation hints (still not a Blueprint clone)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    graph: WorkflowGraph
    viewport: CanvasViewport = Field(default_factory=CanvasViewport)
    notes: str | None = None
