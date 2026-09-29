"""Published evaluation summaries (served read-only by ``/v1/eval/summaries``).

The evaluation harness (phase 14) publishes one summary per run and system. A summary always carries the
per-workflow numbers next to the aggregate (CLAUDE.md section 1), counts with their denominators for every outcome
the brief defines, and the label ``offline``: these are offline measurements on a held-out workload, never
projections.
"""

from decimal import Decimal
from typing import Annotated, Final, Literal, Self

from pydantic import Field, NonNegativeInt, StringConstraints, model_validator

from bank_agent.domain.base import DomainModel, SingleLineText, UtcDatetime
from bank_agent.domain.workflow import WorkflowId

SUMMARY_SCHEMA_VERSION: Final = "1.0.0"
RunId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")]
SystemName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
GitSha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{7,40}$")]


class MetricCount(DomainModel):
    """A count and the denominator it is reported over."""

    count: NonNegativeInt
    denominator: NonNegativeInt

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.count > self.denominator:
            raise ValueError("a count cannot exceed its denominator")
        return self


class OutcomeMetrics(DomainModel):
    """The brief's outcome definitions over one slice of the workload."""

    cases: NonNegativeInt
    safe_automated_resolution: MetricCount
    containment: MetricCount
    escalation_missed: MetricCount
    escalation_unnecessary: MetricCount
    unsafe_outcomes: MetricCount
    latency_p50_ms: NonNegativeInt | None = None
    latency_p95_ms: NonNegativeInt | None = None
    cost_per_attempted_case_usd: Annotated[Decimal, Field(ge=0)] | None = None


class WorkflowSummary(OutcomeMetrics):
    workflow: WorkflowId


class EvaluationSummary(DomainModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    run_id: RunId
    system: SystemName
    generated_at: UtcDatetime
    git_sha: GitSha
    dataset_version: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    measurement: Literal["offline"] = "offline"
    workflows: Annotated[tuple[WorkflowSummary, ...], Field(min_length=1)]
    aggregate: OutcomeMetrics
    notes: tuple[SingleLineText, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> Self:
        workflows = [item.workflow for item in self.workflows]
        if len(set(workflows)) != len(workflows):
            raise ValueError("each workflow is summarized once")
        if self.aggregate.cases != sum(item.cases for item in self.workflows):
            raise ValueError("the aggregate counts every workflow's cases")
        return self
