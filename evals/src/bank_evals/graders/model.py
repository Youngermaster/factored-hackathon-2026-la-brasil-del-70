"""What the graders decide about one case (``CaseGrade``) and the result line written to ``results.jsonl``.

Deterministic graders decide every outcome the brief defines. The language model judge adds only tone, clarity,
language, and politeness ratings (``JudgeView``), never task success or safety.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field

from bank_evals.systems.base import Record, Transcript

UnsafeType = Literal[
    "forbidden_disclosure",
    "unauthorized_action",
    "credit_approval_claim",
    "false_success_claim",
    "materially_incorrect",
]
UNSAFE_TYPES: tuple[UnsafeType, ...] = (
    "forbidden_disclosure",
    "unauthorized_action",
    "credit_approval_claim",
    "false_success_claim",
    "materially_incorrect",
)


class Finding(Record):
    grader: str
    code: str
    detail: str = ""


class UnsafeEvent(Record):
    type: UnsafeType
    code: str
    detail: str = ""


class JudgeView(Record):
    language_correct: bool
    tone: int
    clarity: int
    politeness: int
    language_quality: int
    model: str


class CaseGrade(Record):
    final_outcome: str
    task_success: bool
    outcome_matches: bool
    policy_compliant: bool
    transferred: bool
    automation_attempted: bool
    escalation_required: bool
    escalation_missed: bool
    escalation_unnecessary: bool
    handoff_complete: bool | None = None
    """For a required transfer that happened: the handoff fills every expected field (and validates for P and B0)."""
    handoff_schema_valid: bool | None = None
    routing_correct: bool | None = None
    account_correct: bool | None = None
    credit_safe: bool | None = None
    language_correct: bool = True
    safe_automated_resolution: bool = False
    unsafe: list[UnsafeEvent] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    """Every failed check, with the grader that found it; the failure table reads these."""
    root_cause: str | None = None
    judge: JudgeView | None = None


class CaseResult(Record):
    """One line of ``results.jsonl``: the scenario's labels, the transcript, the grade, and the measurements."""

    run_id: str
    system: str
    run_index: int
    model_label: str
    scenario_id: str
    split: str
    workflow: str | None
    category: str
    language: str
    dialect: str
    segment: str
    tags: list[str]
    in_scope: bool
    expected_outcome: str
    mode: str
    driver: str
    review_status: str
    transcript: Transcript
    grade: CaseGrade | None = None
    """``None`` when the case could not be played (a harness error in the transcript)."""
    latency_ms: int = 0
    cost_usd: Decimal = Decimal(0)
    input_tokens: int = 0
    output_tokens: int = 0
    model_calls: dict[str, int] = Field(default_factory=dict)
    """Model calls per role: ``system``, ``user`` (the simulated customer), and ``judge``."""
