"""The published summary of one system in one run: ``EvaluationSummary`` schema 1.1.0, the shape the phase 13
evaluation view reads from ``/v1/eval/summaries``.

Every summary is labeled ``simulated``: the customers are scripted or played by a model, on a synthetic world.
Latency is per turn, end to end in process. The model and provider label, the split, the scenario set hash, and
the cassette coverage travel in the notes, so no number is shown without them.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from bank_agent.domain.evaluation import (
    EvaluationSummary,
    MetricCount,
    OutcomeMetrics,
    SliceSummary,
    WorkflowSummary,
)
from bank_agent.domain.workflow import WorkflowId
from bank_evals.metrics.compute import WORKFLOWS

SUMMARY_DIMENSIONS = ("language", "dialect", "segment")


def _count(block: dict[str, Any], name: str) -> MetricCount:
    return MetricCount(count=block[name]["count"], denominator=block[name]["denominator"])


def _money(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def outcome_fields(block: dict[str, Any]) -> dict[str, Any]:
    return {
        "cases": block["cases"],
        "safe_automated_resolution": _count(block, "safe_automated_resolution"),
        "containment": _count(block, "containment"),
        "escalation_missed": _count(block, "escalation_missed"),
        "escalation_unnecessary": _count(block, "escalation_unnecessary"),
        "unsafe_outcomes": _count(block, "unsafe_outcomes"),
        "latency_p50_ms": block["latency_turn_p50_ms"],
        "latency_p95_ms": block["latency_turn_p95_ms"],
        "cost_per_attempted_case_usd": _money(block["cost_per_attempted_case_usd"]),
        "automation_attempted": _count(block, "automation_attempted"),
        "cost_per_resolution_usd": _money(block["cost_per_resolution_usd"]),
    }


def build_summary(
    *,
    run_id: str,
    system: str,
    metrics: dict[str, Any],
    generated_at: datetime,
    git_sha: str,
    dataset_version: str,
    failure_table: str | None,
    notes: Sequence[str],
) -> EvaluationSummary:
    workflows = tuple(
        WorkflowSummary(workflow=WorkflowId(name), **outcome_fields(metrics["workflows"][name])) for name in WORKFLOWS
    )
    breakdowns: list[SliceSummary] = []
    for dimension in SUMMARY_DIMENSIONS:
        for value, block in metrics["slices"][dimension].items():
            breakdowns.append(SliceSummary(dimension=dimension, value=value, **outcome_fields(block)))  # type: ignore[arg-type]
        for name in WORKFLOWS:
            for value, block in metrics["workflow_slices"][name][dimension].items():
                breakdowns.append(
                    SliceSummary(
                        dimension=dimension,  # type: ignore[arg-type]
                        value=value,
                        workflow=WorkflowId(name),
                        **outcome_fields(block),
                    )
                )
    return EvaluationSummary(
        run_id=run_id,
        system=system,
        generated_at=generated_at,
        git_sha=git_sha,
        dataset_version=dataset_version,
        measurement="simulated",
        workflows=workflows,
        aggregate=OutcomeMetrics(**outcome_fields(metrics["aggregate"])),
        breakdowns=tuple(breakdowns),
        failure_table=failure_table,
        notes=tuple(notes),
    )
