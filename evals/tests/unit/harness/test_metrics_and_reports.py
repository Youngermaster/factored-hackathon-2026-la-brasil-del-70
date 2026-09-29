"""Slice metrics, the run metrics, the published summary 1.1.0, and the Markdown reports."""

from datetime import UTC, datetime
from decimal import Decimal

from bank_evals_support import result, scenario

from bank_agent.domain.evaluation import EvaluationSummary
from bank_evals.graders.model import CaseGrade, CaseResult, UnsafeEvent
from bank_evals.metrics.aggregate import slice_metrics
from bank_evals.metrics.compute import disparities, repeated, system_metrics
from bank_evals.reports.markdown import render_failures, render_report
from bank_evals.reports.summary import build_summary
from bank_evals.reports.tables import rate, unsafe_rate

WORKFLOW_PERSONA = {"account_inquiry": "acc-mx", "card_support": "crd-mx", "dispute": "dsp-mx", "credit": "cre-mx"}


def grade_(*, sar: bool = True, escalate: bool = False, transferred: bool = False, unsafe: bool = False) -> CaseGrade:
    return CaseGrade(
        final_outcome="escalated" if transferred else "resolved", task_success=sar, outcome_matches=sar,
        policy_compliant=True, transferred=transferred, automation_attempted=not transferred,
        escalation_required=escalate, escalation_missed=escalate and not transferred,
        escalation_unnecessary=transferred and not escalate,
        handoff_complete=True if escalate and transferred else None,
        safe_automated_resolution=sar and not escalate and not transferred and not unsafe,
        unsafe=[UnsafeEvent(type="forbidden_disclosure", code="x")] if unsafe else [],
    )  # fmt: skip


def cases(system: str = "p", run_index: int = 1) -> list[CaseResult]:
    out = []
    for number, workflow in enumerate(WORKFLOW_PERSONA):
        base = {"workflow": workflow, "persona_ref": WORKFLOW_PERSONA[workflow]}
        out.append(result(scenario(id=f"s-{workflow[:3]}-1", **base), grade_(), system, run_index, latency=10 + number))
        out.append(result(scenario(id=f"s-{workflow[:3]}-2", language="pt", dialect="pt-BR", **base),
                          grade_(sar=False, unsafe=True), system, run_index, segment="premium"))  # fmt: skip
        esc = scenario(id=f"s-{workflow[:3]}-3", expected_outcome="escalated", **base)
        out.append(result(esc, grade_(sar=True, escalate=True, transferred=True), system, run_index))
    routing = scenario(
        id="s-rtg-1",
        workflow=None,
        in_scope=False,
        expected_outcome="abstained",
        category="unsupported",
        tags=["routing"],
    )
    out.append(result(routing, grade_(), system, run_index))
    return out


def test_slice_metrics_follow_the_plan_definitions() -> None:
    metrics = slice_metrics([r for r in cases() if r.workflow == "card_support"])
    assert (metrics.cases, metrics.in_scope) == (3, 3)
    assert (metrics.safe_automated_resolution.count, metrics.safe_automated_resolution.denominator) == (1, 3)
    assert (metrics.containment.count, metrics.escalation_missed.denominator) == (2, 1)
    assert metrics.handoff_complete.count == 1
    assert metrics.unsafe_outcomes.count == 1
    assert metrics.unsafe_by_type["forbidden_disclosure"].count == 1
    assert metrics.small_cell
    assert metrics.cost_per_resolution_usd == Decimal(0)


def test_cost_per_resolution_is_not_defined_without_a_resolution() -> None:
    none = slice_metrics([result(scenario(), grade_(sar=False))])
    assert none.cost_per_resolution_usd is None
    errored = slice_metrics([result(scenario(), None)])
    assert errored.harness_errors == 1
    assert errored.cases == 0


def test_system_metrics_keep_workflows_aggregate_routing_and_slices() -> None:
    data = system_metrics(cases())
    assert data["aggregate"]["cases"] == sum(data["workflows"][w]["cases"] for w in WORKFLOW_PERSONA) == 12
    assert data["routing"]["cases"] == 1
    assert set(data["slices"]["language"]) == {"es", "pt"}
    assert "premium" in data["slices"]["segment"]
    assert data["repeated"] == {"scenarios": 0}


def test_disparities_list_a_gap_of_ten_points_or_more() -> None:
    found = disparities(cases())
    assert {(d["workflow"], d["dimension"], d["value"]) for d in found} >= {("card_support", "language", "pt")}
    assert all(d["status"] == "not established (small sample)" for d in found)


def test_repeated_runs_give_pass_hat_k_and_between_run_variance() -> None:
    runs = cases("p", 1) + cases("p", 2)
    rep = repeated(runs)
    assert rep["scenarios"] == 13
    assert rep["runs"] == 2
    assert rep["pass_hat_k"]["2"] <= rep["pass_hat_k"]["1"]
    assert rep["between_run_sd"] == 0.0
    assert rep["flip_share"] == 0.0


def test_the_summary_is_a_valid_1_1_0_document_with_breakdowns() -> None:
    summary = build_summary(
        run_id="fixture-run", system="p", metrics=system_metrics(cases()),
        generated_at=datetime(2026, 9, 29, tzinfo=UTC),
        git_sha="abcdef1", dataset_version="eval-world-1:test:abc", failure_table="docs/evaluation/failures.md",
        notes=["Model and provider: none."],
    )  # fmt: skip
    document = EvaluationSummary.model_validate_json(summary.model_dump_json())
    assert document.schema_version == "1.1.0"
    assert document.measurement == "simulated"
    assert [w.workflow.value for w in document.workflows] == list(WORKFLOW_PERSONA)
    assert any(b.workflow is not None for b in document.breakdowns)
    assert document.aggregate.automation_attempted is not None


def test_rates_show_wilson_intervals_and_zero_event_bounds() -> None:
    assert rate({"count": 18, "denominator": 20}) == "18/20 (90%, 70 to 97)"
    assert "not defined" in rate({"count": 0, "denominator": 0})
    assert "95% upper bound 9.5%" in unsafe_rate({"count": 0, "denominator": 30})
    assert "exact 95%" in unsafe_rate({"count": 2, "denominator": 30})


def test_reports_have_one_section_per_workflow_and_label_the_measurement() -> None:
    manifest = {"run_id": "r", "generated_at": "2026-09-29T00:00:00+00:00", "git_sha": "abc1234", "split": "dev",
                "scenario_file": "scenarios.dev.jsonl", "scenario_set_hash": "0" * 64, "scenarios": 13, "runs": 1,
                "llm_mode": "off", "systems": {"p": "none"}, "cassette_misses": {}, "harness_errors": 0}  # fmt: skip
    results = cases()
    report = render_report(manifest, {"p": system_metrics(results)}, results)
    for heading in ("## `account_inquiry`", "## `credit`", "## Aggregate", "## Routing scenarios", "### By dialect"):
        assert heading in report
    assert "simulated, offline" in report
    failures = render_failures(manifest, results)
    assert "`s-car-2`" in failures
    assert "Root causes: none 1." in failures
