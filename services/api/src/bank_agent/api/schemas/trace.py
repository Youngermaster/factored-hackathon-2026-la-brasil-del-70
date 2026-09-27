"""Execution records for the glass box, in a customer view and a staff (evaluator) view.

Risk estimates follow the phase 02b visibility rule: the evaluator view includes them; the customer view shows only
that an estimate was used and by which model, never the probability, interval, band, or flags. The customer view
also leaves out the session id, trust events, the risk tier, and safety interventions, which describe the
system's defenses rather than the customer's request. Neither view has a reasoning field (ADR 0006).
"""

from datetime import datetime
from decimal import Decimal

from bank_agent.api.schemas.base import ResponseModel
from bank_agent.domain.access import AuthLevel, Channel
from bank_agent.domain.decision import ClauseRef, Decision
from bank_agent.domain.eligibility import EligibilityAssessmentRecord, RiskEstimateRecord
from bank_agent.domain.execution_record import (
    ExecutionRecord,
    GroundingReport,
    LatencyBreakdown,
    LlmCallRecord,
    RetrievalRecord,
    ToolCallRecord,
)
from bank_agent.domain.identifiers import CaseId, ConversationId, HandoffId, RiskEstimateId, TurnId
from bank_agent.domain.intelligence import IntentPrediction, LanguageDetection, ModelRef, PromptRef, TokenUsage
from bank_agent.domain.locale import Language
from bank_agent.domain.trust import RiskTier, TrustEventKind
from bank_agent.domain.workflow import Outcome, StateName, WorkflowRef


class RiskEstimateUsed(ResponseModel):
    """That a risk estimate was used, and which model made it. No value of the estimate."""

    estimate_id: RiskEstimateId
    model: ModelRef
    label_definition: str


class TraceRecordBase(ResponseModel):
    schema_version: str
    turn_id: TurnId
    conversation_id: ConversationId
    workflow: WorkflowRef
    workflow_before: WorkflowRef | None
    recorded_at: datetime
    channel: Channel
    language: Language | None
    language_detection: LanguageDetection | None
    auth_level: AuthLevel
    state_before: StateName
    state_after: StateName
    outcome: Outcome
    intent: IntentPrediction | None
    decisions: tuple[Decision, ...]
    clause_refs: tuple[ClauseRef, ...]
    tool_calls: tuple[ToolCallRecord, ...]
    llm_calls: tuple[LlmCallRecord, ...]
    models: tuple[ModelRef, ...]
    prompts: tuple[PromptRef, ...]
    policy_pack_version: str
    latency: LatencyBreakdown
    token_usage: TokenUsage
    cost_usd: Decimal
    grounding: GroundingReport
    handoff_ref: HandoffId | None
    case_refs: tuple[CaseId, ...]
    eligibility_assessments: tuple[EligibilityAssessmentRecord, ...]
    retrieval: RetrievalRecord | None


class CustomerTraceRecord(TraceRecordBase):
    risk_estimates_used: tuple[RiskEstimateUsed, ...]

    @classmethod
    def of(cls, record: ExecutionRecord) -> "CustomerTraceRecord":
        used = tuple(
            RiskEstimateUsed(estimate_id=item.estimate_id, model=item.model, label_definition=item.label_definition)
            for item in record.risk_estimates
        )
        return cls.model_validate({**_fields(record, TraceRecordBase), "risk_estimates_used": used})


class StaffTraceRecord(TraceRecordBase):
    """The evaluator view: everything in the record, the internal risk estimates included."""

    risk_estimates: tuple[RiskEstimateRecord, ...]
    risk_tier: RiskTier
    trust_events_added: tuple[TrustEventKind, ...]
    safety_interventions: tuple[str, ...]
    trace_id: str | None

    @classmethod
    def of(cls, record: ExecutionRecord) -> "StaffTraceRecord":
        return cls.model_validate(_fields(record, cls))


def _fields(record: ExecutionRecord, model: type[ResponseModel]) -> dict[str, object]:
    return {name: getattr(record, name) for name in model.model_fields if hasattr(record, name)}


class CustomerTraceResponse(ResponseModel):
    conversation_id: ConversationId
    records: tuple[CustomerTraceRecord, ...]


class StaffTraceResponse(ResponseModel):
    conversation_id: ConversationId
    records: tuple[StaffTraceRecord, ...]
