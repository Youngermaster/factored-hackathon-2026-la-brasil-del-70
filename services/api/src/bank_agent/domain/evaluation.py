"""Published evaluation summaries (served read-only by ``/v1/eval/summaries``).

The evaluation harness (phase 14) publishes one summary per run and system. A summary always carries the
per-workflow numbers next to the aggregate (CLAUDE.md section 1) and counts with their denominators for every
outcome the brief defines. Every summary is labeled with how its numbers were obtained, and the label is always
shown next to them: ``offline`` (measured on a held-out workload), ``simulated`` (measured against simulated
customers or traffic), or ``projected`` (extrapolated from measurements under stated assumptions, never a
measurement itself).

Schema 1.1.0 is additive: every metrics block gains the attempted-automation count and the cost per successful
resolution, and a summary gains the ``simulated`` and ``projected`` labels, breakdowns by language, dialect, or
segment (optionally per workflow), and the repository path of its failure table. A 1.0.0 file still loads and
cannot carry any of them.
"""

from decimal import Decimal
from typing import Annotated, Final, Literal, Self

from pydantic import Field, NonNegativeInt, StringConstraints, model_validator

from bank_agent.domain.base import DomainModel, SingleLineText, UtcDatetime
from bank_agent.domain.workflow import WorkflowId

SUMMARY_SCHEMA_VERSION: Final = "1.1.0"
RunId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")]
SystemName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
GitSha = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{7,40}$")]
SliceValue = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{0,31}$")]
RepositoryPath = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_./-]{1,200}$")]
Measurement = Literal["offline", "simulated", "projected"]
SliceDimension = Literal["language", "dialect", "segment"]


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
    automation_attempted: MetricCount | None = None
    """Cases where automation was attempted, over all in-scope cases (added in 1.1.0)."""
    cost_per_resolution_usd: Annotated[Decimal, Field(ge=0)] | None = None
    """Cost per successful resolution (added in 1.1.0)."""

    def carries_1_1_fields(self) -> bool:
        return self.automation_attempted is not None or self.cost_per_resolution_usd is not None


class WorkflowSummary(OutcomeMetrics):
    workflow: WorkflowId


class SliceSummary(OutcomeMetrics):
    """The outcome metrics for one slice, for example ``language`` ``pt`` or ``segment`` ``premium`` (added in 1.1.0).

    ``workflow`` is ``None`` for a slice across every workflow.
    """

    dimension: SliceDimension
    value: SliceValue
    workflow: WorkflowId | None = None


class EvaluationSummary(DomainModel):
    schema_version: Literal["1.0.0", "1.1.0"] = "1.1.0"
    run_id: RunId
    system: SystemName
    generated_at: UtcDatetime
    git_sha: GitSha
    dataset_version: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    measurement: Measurement = "offline"
    workflows: Annotated[tuple[WorkflowSummary, ...], Field(min_length=1)]
    aggregate: OutcomeMetrics
    breakdowns: tuple[SliceSummary, ...] = ()
    failure_table: RepositoryPath | None = None
    """The repository-relative path of the run's failure table (added in 1.1.0)."""
    notes: tuple[SingleLineText, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> Self:
        workflows = [item.workflow for item in self.workflows]
        if len(set(workflows)) != len(workflows):
            raise ValueError("each workflow is summarized once")
        if self.aggregate.cases != sum(item.cases for item in self.workflows):
            raise ValueError("the aggregate counts every workflow's cases")
        slices = [(item.dimension, item.value, item.workflow) for item in self.breakdowns]
        if len(set(slices)) != len(slices):
            raise ValueError("each (dimension, value, workflow) slice is summarized once")
        table = self.failure_table
        if table is not None and (table.startswith("/") or ".." in table):
            raise ValueError("the failure table is a relative path inside the repository")
        if self.schema_version == "1.0.0" and self._carries_1_1_data():
            raise ValueError("a 1.0.0 summary cannot carry fields added in 1.1.0")
        return self

    def _carries_1_1_data(self) -> bool:
        blocks: list[OutcomeMetrics] = [self.aggregate, *self.workflows]
        return (
            self.measurement != "offline"
            or bool(self.breakdowns)
            or self.failure_table is not None
            or any(block.carries_1_1_fields() for block in blocks)
        )
