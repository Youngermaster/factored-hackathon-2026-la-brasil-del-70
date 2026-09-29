"""The brief's outcome metrics over a slice of graded cases (``SliceMetrics``), exactly as the plan defines them.

Denominators: safe automated resolution, automation attempted, and containment over the in-scope cases of the
slice; missed transfers over the cases that require escalation; unnecessary transfers over those that do not;
handoff completeness over the required transfers that happened; unsafe outcomes over every case of the slice;
routing accuracy over the cases with a routing expectation. Cases with a harness error are excluded and counted.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from bank_evals.graders.model import UNSAFE_TYPES, CaseResult
from bank_evals.metrics.stats import percentile

SMALL_CELL = 30


class Count(BaseModel):
    model_config = ConfigDict(frozen=True)

    count: int
    denominator: int

    @property
    def rate(self) -> float | None:
        return self.count / self.denominator if self.denominator else None


class SliceMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cases: int
    in_scope: int
    harness_errors: int = 0
    safe_automated_resolution: Count
    automation_attempted: Count
    containment: Count
    escalation_missed: Count
    escalation_unnecessary: Count
    handoff_complete: Count
    unsafe_outcomes: Count
    unsafe_by_type: dict[str, Count] = Field(default_factory=dict)
    task_success: Count
    policy_compliant: Count
    routing_correct: Count
    language_correct: Count
    latency_turn_p50_ms: int | None = None
    latency_turn_p95_ms: int | None = None
    latency_case_p50_ms: int | None = None
    latency_case_p95_ms: int | None = None
    cost_total_usd: Decimal = Decimal(0)
    cost_per_attempted_case_usd: Decimal | None = None
    cost_per_resolution_usd: Decimal | None = None
    """``None`` means "not defined": no safe automated resolution in the slice."""
    input_tokens: int = 0
    output_tokens: int = 0
    small_cell: bool = False


def _count(items: Iterable[bool]) -> Count:
    values = list(items)
    return Count(count=sum(values), denominator=len(values))


def slice_metrics(results: Sequence[CaseResult]) -> SliceMetrics:
    graded = [r for r in results if r.grade is not None]
    grades = [r.grade for r in graded if r.grade is not None]
    in_scope = [r for r in graded if r.in_scope]
    scoped = [r.grade for r in in_scope if r.grade is not None]
    required = [g for g in grades if g.escalation_required]
    not_required = [g for g in grades if not g.escalation_required]
    unsafe_types: Counter[str] = Counter()
    for grade in grades:
        for kind in {event.type for event in grade.unsafe}:
            unsafe_types[kind] += 1
    turn_latency = [t.latency_ms for r in graded for t in r.transcript.turns]
    case_latency = [r.latency_ms for r in graded]
    cost = sum((r.cost_usd for r in graded), Decimal(0))
    attempted = sum(g.automation_attempted for g in scoped)
    resolutions = sum(g.safe_automated_resolution for g in scoped)
    return SliceMetrics(
        cases=len(graded),
        in_scope=len(in_scope),
        harness_errors=len(results) - len(graded),
        safe_automated_resolution=_count(g.safe_automated_resolution for g in scoped),
        automation_attempted=_count(g.automation_attempted for g in scoped),
        containment=_count(not g.transferred for g in scoped),
        escalation_missed=_count(g.escalation_missed for g in required),
        escalation_unnecessary=_count(g.escalation_unnecessary for g in not_required),
        handoff_complete=_count(bool(g.handoff_complete) for g in required if g.transferred),
        unsafe_outcomes=_count(bool(g.unsafe) for g in grades),
        unsafe_by_type={kind: Count(count=unsafe_types[kind], denominator=len(grades)) for kind in UNSAFE_TYPES},
        task_success=_count(g.task_success for g in grades),
        policy_compliant=_count(g.policy_compliant for g in grades),
        routing_correct=_count(bool(g.routing_correct) for g in grades if g.routing_correct is not None),
        language_correct=_count(g.language_correct for g in grades),
        latency_turn_p50_ms=_int(percentile(turn_latency, 50)),
        latency_turn_p95_ms=_int(percentile(turn_latency, 95)),
        latency_case_p50_ms=_int(percentile(case_latency, 50)),
        latency_case_p95_ms=_int(percentile(case_latency, 95)),
        cost_total_usd=cost,
        cost_per_attempted_case_usd=(cost / attempted).quantize(Decimal("0.000001")) if attempted else None,
        cost_per_resolution_usd=(cost / resolutions).quantize(Decimal("0.000001")) if resolutions else None,
        input_tokens=sum(r.input_tokens for r in graded),
        output_tokens=sum(r.output_tokens for r in graded),
        small_cell=len(graded) < SMALL_CELL,
    )


def _int(value: float | None) -> int | None:
    return None if value is None else int(value)
