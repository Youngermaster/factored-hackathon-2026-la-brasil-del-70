"""Turn metrics come from the execution record, use catalog names only, and carry ids and codes only."""

from decimal import Decimal

from bank_agent.adapters.telemetry.catalog import CATALOG
from bank_agent.application.engine.metrics import TurnMetrics
from bank_agent.domain.actions import ToolName
from bank_agent.domain.eligibility import EligibilityAssessmentRecord
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.execution_record import (
    GroundingReport,
    LlmCallRecord,
    LlmCallStatus,
    ToolCallRecord,
    ToolCallStatus,
)
from bank_agent.domain.intelligence import PromptRef
from bank_agent.domain.workflow import Outcome, WorkflowRef
from bank_agent.testing.telemetry import RecordingTelemetry
from bank_agent_builders import eligibility_assessment, execution_record


def _tool(sequence: int, status: ToolCallStatus, error: str | None = None) -> ToolCallRecord:
    return ToolCallRecord(
        sequence=sequence, tool=ToolName.GET_TRANSACTION, status=status, attempts=1, latency_ms=40, error_code=error
    )


def test_a_turn_records_latency_outcome_tools_and_fallbacks() -> None:
    telemetry = RecordingTelemetry()
    fallback = LlmCallRecord(
        prompt=PromptRef(prompt_id="extract_dispute_slots", version=1),
        model_id="gateway/unavailable",
        input_tokens=0,
        output_tokens=0,
        cost_usd=Decimal(0),
        latency_ms=0,
        status=LlmCallStatus.FALLBACK,
        error_code="llm_circuit_open",
    )
    record = execution_record(
        tool_calls=[_tool(1, ToolCallStatus.OK), _tool(2, ToolCallStatus.FAILED, "tool_timeout")],
        llm_calls=[fallback],
        workflow_before=WorkflowRef(id="card_support", version=1),
    )
    TurnMetrics(telemetry).observe(record)

    assert telemetry.histograms["bank.turn.duration"].values == [
        (0.12, {"bank.workflow": "dispute", "bank.outcome": "in_progress"})
    ]
    assert telemetry.counters["bank.turn.outcomes"].points == [
        (1, {"bank.workflow": "dispute", "bank.outcome": "in_progress", "bank.language": "es"})
    ]
    assert [attrs for _, attrs in telemetry.counters["bank.tool.calls"].points] == [
        {"bank.tool": "get_transaction", "bank.tool.status": "ok"},
        {"bank.tool": "get_transaction", "bank.tool.status": "failed"},
    ]
    assert telemetry.counters["bank.tool.failures"].points == [
        (1, {"bank.tool": "get_transaction", "error.type": "tool_timeout"})
    ]
    assert telemetry.counters["bank.router.switches"].points == [
        (1, {"bank.workflow.from": "card_support", "bank.workflow": "dispute"})
    ]
    assert telemetry.counters["bank.llm.fallbacks"].points == [
        (1, {"bank.prompt.id": "extract_dispute_slots", "error.type": "llm_circuit_open", "bank.workflow": "dispute"})
    ]
    assert telemetry.counters["bank.escalations"].total == 0


def test_escalations_eligibility_risk_failures_and_unsafe_detectors() -> None:
    telemetry = RecordingTelemetry()
    assessment = EligibilityAssessmentRecord.from_assessment(eligibility_assessment())
    record = execution_record(
        workflow=WorkflowRef(id="credit", version=1),
        outcome=Outcome.ESCALATED,
        handoff_ref="hof-000001",
        eligibility_assessments=[assessment],
        safety_interventions=["risk_estimate_unavailable"],
        grounding=GroundingReport(violations=("approval_wording", "internal_figure_disclosed", "unsupported_date")),
    )
    TurnMetrics(telemetry).observe(record, escalation_reason="eligibility_review")

    assert telemetry.counters["bank.escalations"].points == [
        (1, {"bank.workflow": "credit", "bank.escalation.reason": "eligibility_review"})
    ]
    assert telemetry.counters["bank.eligibility.outcomes"].points == [
        (1, {"bank.credit.product": "MX-PL-FIXTURE", "bank.eligibility.outcome": "indicatively_eligible"})
    ]
    assert telemetry.counters["bank.risk_estimator.failures"].total == 1
    assert telemetry.counters["bank.safety.interventions"].points == [
        (1, {"bank.intervention": "risk_estimate_unavailable", "bank.workflow": "credit"})
    ]
    assert [attrs["bank.detector"] for _, attrs in telemetry.counters["bank.safety.unsafe_blocked"].points] == [
        "approval_wording",
        "internal_credit_value",
    ]


def test_every_metric_and_attribute_is_in_the_catalog() -> None:
    telemetry = RecordingTelemetry()
    metrics = TurnMetrics(telemetry)
    metrics.observe(execution_record(), escalation_reason="human_requested")
    names = {*telemetry.counters, *telemetry.histograms, *telemetry.gauges}
    assert names <= set(CATALOG)
    for counter in telemetry.counters.values():
        for _, attributes in counter.points:
            assert set(attributes) <= CATALOG[counter.name].attributes, counter.name
    for histogram in telemetry.histograms.values():
        for _, attributes in histogram.values:
            assert set(attributes) <= CATALOG[histogram.name].attributes, histogram.name


def test_outcome_and_handoff_counters_start_at_zero_for_every_known_label_set() -> None:
    """A new series needs a 0 sample before its first event, or Prometheus increase() never counts that event."""
    telemetry = RecordingTelemetry()

    TurnMetrics(telemetry).start_at_zero()

    outcomes = telemetry.counters["bank.turn.outcomes"].points
    escalations = telemetry.counters["bank.escalations"].points
    assert {value for value, _ in outcomes + escalations} == {0}
    workflows = {"router", "account_inquiry", "card_support", "dispute", "credit"}
    assert {attributes["bank.workflow"] for _, attributes in outcomes} == workflows
    assert {attributes["bank.language"] for _, attributes in outcomes} == {"es", "pt", "en", "unknown"}
    assert {attributes["bank.outcome"] for _, attributes in outcomes} == {outcome.value for outcome in Outcome}
    assert len(outcomes) == 5 * 6 * 4
    reasons = {attributes["bank.escalation.reason"] for _, attributes in escalations}
    assert reasons == {reason.value for reason in EscalationReasonCode}
    assert len(escalations) == 5 * len(EscalationReasonCode)
    for counter in ("bank.turn.outcomes", "bank.escalations"):
        allowed = CATALOG[counter].attributes
        assert all(set(attributes) <= allowed for _, attributes in telemetry.counters[counter].points)
