"""``TurnRecorder`` collects what a turn did and assembles its execution record.

It stores rule ids, clause versions, tool calls with redacted arguments and verification, language model calls
(prompt and model versions, tokens, cost, latency), the models used, latency per stage, trust events, and safety
interventions. It never stores model reasoning: there is no field for it, and the record explains a decision
through rules, clauses, and outcomes (ADR 0006).
"""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal

from pydantic import BaseModel

from bank_agent.application.grounding.draft import VerifiedAction
from bank_agent.domain.decision import ClauseRef, Decision
from bank_agent.domain.eligibility import EligibilityAssessmentRecord, RiskEstimateRecord
from bank_agent.domain.errors import LlmError
from bank_agent.domain.execution_record import (
    GroundingReport,
    LatencyBreakdown,
    LlmCallRecord,
    LlmCallStatus,
    RetrievalRecord,
    ToolCallRecord,
)
from bank_agent.domain.identifiers import CaseId
from bank_agent.domain.intelligence import ModelRef, PromptRef, StructuredGeneration, TextGeneration, TokenUsage
from bank_agent.domain.trust import TrustEventKind

UNAVAILABLE_MODEL = "gateway/unavailable"


def _milliseconds(seconds: float) -> int:
    return max(0, round(seconds * 1000))


@dataclass
class TurnRecorder:
    monotonic: Callable[[], float] = time.perf_counter
    decisions: list[Decision] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    llm_calls: list[LlmCallRecord] = field(default_factory=list)
    models: dict[str, ModelRef] = field(default_factory=dict)
    prompts: dict[str, PromptRef] = field(default_factory=dict)
    verified_actions: list[VerifiedAction] = field(default_factory=list)
    stages: dict[str, int] = field(default_factory=dict)
    trust_events: list[TrustEventKind] = field(default_factory=list)
    safety: list[str] = field(default_factory=list)
    case_refs: list[CaseId] = field(default_factory=list)
    citations: list[ClauseRef] = field(default_factory=list)
    retrieval: RetrievalRecord | None = None
    grounding: GroundingReport = field(default_factory=GroundingReport)
    risk_estimates: list[RiskEstimateRecord] = field(default_factory=list)
    """Credit turns: each estimate the engine obtained, kept apart from the assessments (never merged)."""
    eligibility_assessments: list[EligibilityAssessmentRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._started = self.monotonic()

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started = self.monotonic()
        try:
            yield
        finally:
            self.stages[name] = self.stages.get(name, 0) + _milliseconds(self.monotonic() - started)

    def elapsed_ms(self) -> int:
        return _milliseconds(self.monotonic() - self._started)

    def latency(self) -> LatencyBreakdown:
        total = max([self.elapsed_ms(), *self.stages.values()])
        return LatencyBreakdown(total_ms=total, stages=dict(self.stages))

    def decision(self, decision: Decision) -> Decision:
        self.decisions.append(decision)
        return decision

    def model(self, ref: ModelRef) -> None:
        self.models.setdefault(str(ref), ref)

    def next_tool_sequence(self) -> int:
        return len(self.tool_calls) + 1

    def tool_call(self, record: ToolCallRecord) -> None:
        self.tool_calls.append(record)

    def intervention(self, code: str) -> None:
        if code not in self.safety:
            self.safety.append(code)

    def llm_success[OutputT: BaseModel](self, generation: StructuredGeneration[OutputT] | TextGeneration) -> None:
        repaired = isinstance(generation, StructuredGeneration) and generation.repaired
        self.prompts.setdefault(str(generation.prompt), generation.prompt)
        self.llm_calls.append(
            LlmCallRecord(
                prompt=generation.prompt,
                model_id=generation.model_id,
                input_tokens=generation.usage.input_tokens,
                output_tokens=generation.usage.output_tokens,
                cost_usd=generation.cost_usd or Decimal(0),
                latency_ms=generation.latency_ms,
                status=LlmCallStatus.REPAIRED if repaired else LlmCallStatus.OK,
            )
        )

    def llm_failure(self, prompt: PromptRef, error: LlmError, latency_ms: int = 0) -> None:
        self.prompts.setdefault(str(prompt), prompt)
        self.llm_calls.append(
            LlmCallRecord(
                prompt=prompt,
                model_id=UNAVAILABLE_MODEL,
                input_tokens=0,
                output_tokens=0,
                cost_usd=Decimal(0),
                latency_ms=latency_ms,
                status=LlmCallStatus.FALLBACK,
                error_code=error.code,
            )
        )
        self.intervention("llm_fallback")

    def llm_skipped(self, prompt: PromptRef, code: str) -> None:
        """A model call not attempted (template-only mode): recorded like a fallback, with the reason as its code."""
        self.prompts.setdefault(str(prompt), prompt)
        self.llm_calls.append(
            LlmCallRecord(
                prompt=prompt,
                model_id=UNAVAILABLE_MODEL,
                input_tokens=0,
                output_tokens=0,
                cost_usd=Decimal(0),
                latency_ms=0,
                status=LlmCallStatus.FALLBACK,
                error_code=code,
            )
        )
        self.intervention("llm_fallback")

    def token_usage(self) -> TokenUsage:
        return sum(
            (TokenUsage(input_tokens=c.input_tokens, output_tokens=c.output_tokens) for c in self.llm_calls),
            TokenUsage(),
        )

    def cost(self) -> Decimal:
        return sum((call.cost_usd for call in self.llm_calls), Decimal(0))

    def clause_refs(self) -> tuple[ClauseRef, ...]:
        seen: dict[ClauseRef, None] = {}
        for decision in self.decisions:
            for ref in decision.clause_refs:
                seen.setdefault(ref, None)
        for ref in self.citations:
            seen.setdefault(ref, None)
        return tuple(seen)
