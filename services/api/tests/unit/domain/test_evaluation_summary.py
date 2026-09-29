"""Evaluation summary schema 1.1.0: labels, breakdowns, attempted automation, cost per resolution, failure table."""

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from bank_agent.domain.evaluation import SUMMARY_SCHEMA_VERSION, EvaluationSummary

COUNT = {"count": 1, "denominator": 2}
METRICS: dict[str, Any] = {
    "cases": 2, "safe_automated_resolution": COUNT, "containment": COUNT, "escalation_missed": COUNT,
    "escalation_unnecessary": COUNT, "unsafe_outcomes": {"count": 0, "denominator": 2},
}  # fmt: skip


def summary(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "run_id": "run-1", "system": "proposed", "generated_at": "2026-09-29T00:00:00Z", "git_sha": "abc1234",
        "dataset_version": "scenarios-v1", "workflows": [{"workflow": "dispute", **METRICS}], "aggregate": METRICS,
    }  # fmt: skip
    return {**document, **overrides}


def test_a_1_0_file_still_loads_and_new_documents_are_1_1_offline() -> None:
    old = EvaluationSummary.model_validate(summary(schema_version="1.0.0"))
    assert (old.schema_version, old.measurement, old.breakdowns, old.failure_table) == ("1.0.0", "offline", (), None)
    assert old.aggregate.automation_attempted is None
    new = EvaluationSummary.model_validate(summary())
    assert new.schema_version == SUMMARY_SCHEMA_VERSION == "1.1.0"
    assert new.measurement == "offline"


def test_a_1_1_summary_carries_every_new_field() -> None:
    metrics = {**METRICS, "automation_attempted": {"count": 2, "denominator": 2}, "cost_per_resolution_usd": "0.04"}
    loaded = EvaluationSummary.model_validate(
        summary(
            measurement="projected",
            workflows=[{"workflow": "dispute", **metrics}],
            aggregate=metrics,
            breakdowns=[
                {"dimension": "language", "value": "pt", **metrics},
                {"dimension": "dialect", "value": "es-mx", "workflow": "dispute", **metrics},
                {"dimension": "segment", "value": "premium", **metrics},
            ],
            failure_table="evals/reports/run-1/failures.csv",
        )
    )
    assert loaded.measurement == "projected"
    assert loaded.aggregate.cost_per_resolution_usd == Decimal("0.04")
    assert loaded.workflows[0].automation_attempted is not None
    assert [(item.dimension, item.value, item.workflow) for item in loaded.breakdowns] == [
        ("language", "pt", None),
        ("dialect", "es-mx", "dispute"),
        ("segment", "premium", None),
    ]
    assert loaded.failure_table == "evals/reports/run-1/failures.csv"
    assert EvaluationSummary.model_validate_json(loaded.model_dump_json()) == loaded


def test_a_slice_is_summarized_once_per_dimension_value_and_workflow() -> None:
    twice = [{"dimension": "language", "value": "es", **METRICS}] * 2
    with pytest.raises(ValidationError, match="summarized once"):
        EvaluationSummary.model_validate(summary(breakdowns=twice))
    per_workflow = [
        {"dimension": "language", "value": "es", **METRICS},
        {"dimension": "language", "value": "es", "workflow": "dispute", **METRICS},
    ]
    assert len(EvaluationSummary.model_validate(summary(breakdowns=per_workflow)).breakdowns) == 2


@pytest.mark.parametrize("value", ["ES", "-es", "es mx", "a" * 33, ""])
def test_a_slice_value_is_a_short_lowercase_code(value: str) -> None:
    with pytest.raises(ValidationError):
        EvaluationSummary.model_validate(summary(breakdowns=[{"dimension": "segment", "value": value, **METRICS}]))


@pytest.mark.parametrize(
    "path", ["/etc/passwd", "../outside.csv", "evals/../../x.csv", "evals/a..b.csv", "evals\\x.csv", "a" * 201, ""]
)
def test_the_failure_table_is_a_relative_path_inside_the_repository(path: str) -> None:
    with pytest.raises(ValidationError):
        EvaluationSummary.model_validate(summary(failure_table=path))


@pytest.mark.parametrize(
    "overrides",
    [
        {"measurement": "simulated"},
        {"breakdowns": [{"dimension": "language", "value": "es", **METRICS}]},
        {"failure_table": "evals/reports/failures.csv"},
        {"aggregate": {**METRICS, "cost_per_resolution_usd": "0.10"}},
        {"workflows": [{"workflow": "dispute", **METRICS, "automation_attempted": COUNT}]},
    ],
)
def test_a_1_0_summary_cannot_carry_fields_added_in_1_1(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match=r"added in 1\.1\.0"):
        EvaluationSummary.model_validate(summary(schema_version="1.0.0", **overrides))


def test_costs_are_never_negative_and_counts_fit_their_denominator() -> None:
    with pytest.raises(ValidationError):
        EvaluationSummary.model_validate(summary(aggregate={**METRICS, "cost_per_resolution_usd": "-1"}))
    with pytest.raises(ValidationError, match="cannot exceed"):
        EvaluationSummary.model_validate(
            summary(aggregate={**METRICS, "automation_attempted": {"count": 3, "denominator": 2}})
        )
    with pytest.raises(ValidationError):
        EvaluationSummary.model_validate(summary(measurement="estimated"))
