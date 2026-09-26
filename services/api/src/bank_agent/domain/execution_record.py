"""The execution record, version 1 (``contracts/schemas/execution_record.v1.json``), minor version 1.1.

One record per turn: the workflow state before and after, the intent, every policy decision with rule ids and
versions, the cited clauses, the tool calls with redacted arguments and verification, the language model calls,
the model, prompt, and policy versions, latency, tokens, cost, and the trace id. There is no free-text
reasoning field by design: the record explains a decision through rules, sources, and outcomes. See ADR 0006.

Version 1.1.0 adds ``workflow_before`` (set when the router moved the conversation in this turn), the risk
estimates, and the eligibility assessments. Estimates and assessments are separate fields and are never merged,
so the glass box shows them apart; the estimates are internal. The new fields are marked ``AddedIn``.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, NonNegativeInt, PositiveInt, StringConstraints, model_validator

from bank_agent.domain.access import AuthLevel, Channel
from bank_agent.domain.actions import ToolName, Verification
from bank_agent.domain.base import AddedIn, Code, DomainModel, Internal, UtcDatetime, check_added_fields
from bank_agent.domain.decision import ClauseRef, Decision
from bank_agent.domain.eligibility import EligibilityAssessmentRecord, RiskEstimateRecord
from bank_agent.domain.handoff import SchemaVersion
from bank_agent.domain.identifiers import (
    CaseId,
    ConversationId,
    CustomerId,
    HandoffId,
    IdempotencyKey,
    SessionId,
    TraceId,
    TurnId,
)
from bank_agent.domain.intelligence import (
    IntentPrediction,
    LanguageDetection,
    ModelId,
    ModelRef,
    PromptRef,
    TokenUsage,
)
from bank_agent.domain.locale import Language
from bank_agent.domain.money import Amount
from bank_agent.domain.trust import RiskTier, TrustEventKind
from bank_agent.domain.workflow import Outcome, StateName, WorkflowRef

REDACTED = "[redacted]"
"""The value that replaces a tool argument outside the redaction allowlist."""

RedactedValue = Annotated[str, StringConstraints(max_length=200)] | int | bool | None
Usd = Annotated[Amount, Field(ge=0)]


class ToolCallStatus(StrEnum):
    OK = "ok"
    NOT_FOUND = "not_found"
    FAILED = "failed"
    UNKNOWN = "unknown"
    REJECTED_BY_ALLOWLIST = "rejected_by_allowlist"


class ToolCallRecord(DomainModel):
    sequence: PositiveInt
    tool: ToolName
    arguments: dict[Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")], RedactedValue] = Field(
        default_factory=dict
    )
    idempotency_key: IdempotencyKey | None = None
    status: ToolCallStatus
    error_code: Code | None = None
    attempts: PositiveInt = 1
    latency_ms: NonNegativeInt
    result_summary: Code | None = None
    verification: Verification | None = None


class LlmCallStatus(StrEnum):
    OK = "ok"
    REPAIRED = "repaired"
    FAILED = "failed"
    FALLBACK = "fallback"


class LlmCallRecord(DomainModel):
    prompt: PromptRef
    model_id: ModelId
    input_tokens: NonNegativeInt
    output_tokens: NonNegativeInt
    cost_usd: Usd
    latency_ms: NonNegativeInt
    status: LlmCallStatus
    error_code: Code | None = None


class LatencyBreakdown(DomainModel):
    total_ms: NonNegativeInt
    stages: dict[Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")], NonNegativeInt] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if any(value > self.total_ms for value in self.stages.values()):
            raise ValueError("no stage can take longer than the whole turn")
        return self


class GroundingReport(DomainModel):
    llm_phrasing_used: bool = False
    template_id: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_.]{0,127}$")] | None = None
    violations: tuple[Code, ...] = ()


class ExecutionRecord(DomainModel):
    schema_version: SchemaVersion = "1.1.0"
    turn_id: TurnId
    conversation_id: ConversationId
    customer_ref: CustomerId | None = None
    session_ref: SessionId | None = None
    workflow: WorkflowRef
    recorded_at: UtcDatetime
    channel: Channel
    language: Language | None = None
    language_detection: LanguageDetection | None = None
    auth_level: AuthLevel
    state_before: StateName
    state_after: StateName
    outcome: Outcome
    intent: IntentPrediction | None = None
    decisions: tuple[Decision, ...] = ()
    clause_refs: tuple[ClauseRef, ...] = ()
    tool_calls: tuple[ToolCallRecord, ...] = ()
    llm_calls: tuple[LlmCallRecord, ...] = ()
    models: tuple[ModelRef, ...] = ()
    prompts: tuple[PromptRef, ...] = ()
    policy_pack_version: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    latency: LatencyBreakdown
    token_usage: TokenUsage = TokenUsage()
    cost_usd: Usd = Decimal(0)
    trace_id: TraceId | None = None
    risk_tier: RiskTier = RiskTier.LOW
    trust_events_added: tuple[TrustEventKind, ...] = ()
    grounding: GroundingReport = GroundingReport()
    safety_interventions: tuple[Code, ...] = ()
    handoff_ref: HandoffId | None = None
    case_refs: tuple[CaseId, ...] = ()
    workflow_before: Annotated[WorkflowRef | None, AddedIn("1.1.0")] = None
    risk_estimates: Annotated[tuple[RiskEstimateRecord, ...], AddedIn("1.1.0"), Internal()] = ()
    eligibility_assessments: Annotated[tuple[EligibilityAssessmentRecord, ...], AddedIn("1.1.0")] = ()

    @model_validator(mode="after")
    def _validate(self) -> Self:
        check_added_fields(self, self.schema_version)
        if self.workflow_before is not None and self.workflow_before == self.workflow:
            raise ValueError("workflow_before is set only when the turn moved to another workflow")
        estimate_ids = [estimate.estimate_id for estimate in self.risk_estimates]
        assessment_ids = [assessment.assessment_id for assessment in self.eligibility_assessments]
        if len(set(estimate_ids)) != len(estimate_ids) or len(set(assessment_ids)) != len(assessment_ids):
            raise ValueError("risk estimates and eligibility assessments are recorded once each")
        usage = sum(
            (TokenUsage(input_tokens=c.input_tokens, output_tokens=c.output_tokens) for c in self.llm_calls),
            TokenUsage(),
        )
        if usage != self.token_usage:
            raise ValueError("token_usage must equal the sum over llm_calls")
        if self.cost_usd != sum((call.cost_usd for call in self.llm_calls), Decimal(0)):
            raise ValueError("cost_usd must equal the sum over llm_calls")
        if [call.sequence for call in self.tool_calls] != list(range(1, len(self.tool_calls) + 1)):
            raise ValueError("tool call sequence numbers must be 1, 2, 3, and so on")
        if self.outcome is Outcome.ESCALATED and self.handoff_ref is None:
            raise ValueError("an escalated turn must reference its handoff")
        return self
