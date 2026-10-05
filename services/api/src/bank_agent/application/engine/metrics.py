"""Turn metrics, read from the execution record after the turn is stored.

The record is the audit artifact, so every counter here agrees with it by construction: turn latency and outcomes by
workflow, handoffs by reason code, router dispatches and workflow switches, tool calls and failures, synthetic
eligibility outcomes, risk estimates that could not be computed, model calls replaced by the deterministic path, and
the unsafe-outcome detectors. A detector is a grounding violation of one of three kinds (a success message without
a verified read-back, approval wording, a risk estimate or credit profile value in customer text); the message that
carried it was never sent (phrasing falls back to the template, a template falls back to a safe reply). Attributes
are workflow ids, codes, and tool names only, never text.
"""

from typing import Final

from bank_agent.application.engine.records import ROUTER_REF
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.execution_record import ExecutionRecord, LlmCallStatus, ToolCallStatus
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Outcome, WorkflowId
from bank_agent.ports.telemetry import AttributeValue, Telemetry

UNSAFE_DETECTORS: Final[dict[str, str]] = {
    "unverified_action_claim": "success_without_verification",
    "unsupported_action_claim": "success_without_verification",
    "approval_wording": "approval_wording",
    "internal_figure_disclosed": "internal_credit_value",
}
"""Grounding violation kind to runtime detector name (``bank.safety.unsafe_blocked``)."""
FAILED_TOOL_STATUSES: Final = frozenset({ToolCallStatus.FAILED, ToolCallStatus.UNKNOWN})
RISK_UNAVAILABLE: Final = "risk_estimate_unavailable"
UNKNOWN_LANGUAGE: Final = "unknown"
METRIC_WORKFLOWS: Final = (ROUTER_REF.id, *(workflow.value for workflow in WorkflowId))
"""Every ``bank.workflow`` a turn metric can carry: the four workflows and the router (out of scope, not yet routed)."""


class TurnMetrics:
    """Emits one set of measurements per stored turn."""

    def __init__(self, telemetry: Telemetry) -> None:
        self._duration = telemetry.histogram("bank.turn.duration")
        self._outcomes = telemetry.counter("bank.turn.outcomes")
        self._escalations = telemetry.counter("bank.escalations")
        self._dispatches = telemetry.counter("bank.router.dispatches")
        self._switches = telemetry.counter("bank.router.switches")
        self._tool_calls = telemetry.counter("bank.tool.calls")
        self._tool_failures = telemetry.counter("bank.tool.failures")
        self._tool_duration = telemetry.histogram("bank.tool.duration")
        self._eligibility = telemetry.counter("bank.eligibility.outcomes")
        self._risk_failures = telemetry.counter("bank.risk_estimator.failures")
        self._fallbacks = telemetry.counter("bank.llm.fallbacks")
        self._unsafe = telemetry.counter("bank.safety.unsafe_blocked")
        self._interventions = telemetry.counter("bank.safety.interventions")

    def start_at_zero(self) -> None:
        """Publish every turn-outcome and handoff series at 0 once, when the process starts.

        Prometheus ``increase()`` needs a sample before the first event of a series, and every worker start begins
        new series (the resource carries a fresh ``service.instance.id``): without this, the first turn or handoff
        of each label set after a deploy is never counted, which matters at demo volumes. Every label is a closed
        enumeration, so this adds a bounded set: 5 workflows x 6 outcomes x 4 languages, and 5 x 16 reason codes.
        """
        languages = (*(language.value for language in Language), UNKNOWN_LANGUAGE)
        for workflow in METRIC_WORKFLOWS:
            for outcome in Outcome:
                for language in languages:
                    attributes: dict[str, AttributeValue] = {
                        "bank.workflow": workflow,
                        "bank.outcome": outcome.value,
                        "bank.language": language,
                    }
                    self._outcomes.add(0, attributes)
            for reason in EscalationReasonCode:
                self._escalations.add(0, {"bank.workflow": workflow, "bank.escalation.reason": reason.value})

    def observe(self, record: ExecutionRecord, *, escalation_reason: str | None = None) -> None:
        """Measure ``record``; ``escalation_reason`` is the reason code of a handoff created in this turn."""
        workflow = record.workflow.id
        per_turn: dict[str, AttributeValue] = {"bank.workflow": workflow, "bank.outcome": record.outcome.value}
        self._duration.record(record.latency.total_ms / 1000, per_turn)
        language = record.language.value if record.language is not None else UNKNOWN_LANGUAGE
        self._outcomes.add(1, {**per_turn, "bank.language": language})
        if escalation_reason is not None:
            self._escalations.add(1, {"bank.workflow": workflow, "bank.escalation.reason": escalation_reason})
        if record.intent is not None:
            self._dispatches.add(1, {"bank.workflow": workflow})
        if record.workflow_before is not None:
            self._switches.add(1, {"bank.workflow.from": record.workflow_before.id, "bank.workflow": workflow})
        for call in record.tool_calls:
            tool = call.tool.value
            self._tool_calls.add(1, {"bank.tool": tool, "bank.tool.status": call.status.value})
            self._tool_duration.record(call.latency_ms / 1000, {"bank.tool": tool})
            if call.status in FAILED_TOOL_STATUSES:
                self._tool_failures.add(1, {"bank.tool": tool, "error.type": call.error_code or "unknown"})
        for assessment in record.eligibility_assessments:
            attributes: dict[str, AttributeValue] = {
                "bank.credit.product": str(assessment.product_code),
                "bank.eligibility.outcome": assessment.outcome.value,
            }
            self._eligibility.add(1, attributes)
        if RISK_UNAVAILABLE in record.safety_interventions:
            self._risk_failures.add(1, {"bank.workflow": workflow})
        for llm_call in record.llm_calls:
            if llm_call.status is LlmCallStatus.FALLBACK:
                error = llm_call.error_code or "unknown"
                prompt = llm_call.prompt.prompt_id
                self._fallbacks.add(1, {"bank.prompt.id": prompt, "error.type": error, "bank.workflow": workflow})
        for code in record.safety_interventions:
            family = "unsupported_request" if code.startswith("unsupported_") else code
            self._interventions.add(1, {"bank.intervention": family, "bank.workflow": workflow})
        for kind in record.grounding.violations:
            detector = UNSAFE_DETECTORS.get(kind)
            if detector is not None:
                self._unsafe.add(1, {"bank.detector": detector, "bank.workflow": workflow})
