"""Test support for the evaluation harness: synthetic scenarios, transcripts, and results (fixtures only)."""

from __future__ import annotations

from typing import Any

from bank_evals.graders.grade import grade
from bank_evals.graders.model import CaseGrade, CaseResult
from bank_evals.scenarios.model import Scenario
from bank_evals.systems.base import EndState, ToolCallView, Transcript, TurnView
from bank_evals.world import build_world
from bank_evals.world.model import World

BASE: dict[str, Any] = {
    "split": "dev",
    "goal": "A fixture goal.",
    "mode": "scripted",
    "in_scope": True,
    "provenance": "team_generated",
    "language": "es",
    "dialect": "es-MX",
    "category": "normal",
    "expected_outcome": "resolved",
    "turns": [{"text": "Hola"}],
}


def scenario(**overrides: Any) -> Scenario:
    document = {"id": "fixture-001", "persona_ref": "crd-mx", "workflow": "card_support", **BASE, **overrides}
    return Scenario.model_validate(document)


def world() -> World:
    return build_world()


def turn(text: str = "Hola", reply: str = "Listo.", outcome: str = "resolved", **extra: Any) -> TurnView:
    fields: dict[str, Any] = {"index": 1, "customer_text": text, "assistant_text": reply, "outcome": outcome}
    fields.setdefault("workflow", extra.pop("workflow", "card_support"))
    return TurnView(**fields, **extra)


def call(tool: str, status: str = "ok", customer_id: str | None = None, **arguments: str) -> ToolCallView:
    return ToolCallView(tool=tool, status=status, arguments=arguments, customer_id=customer_id)


def transcript(turns: list[TurnView], system: str = "p", end: EndState | None = None) -> Transcript:
    return Transcript(
        scenario_id="fixture-001", system=system, model_label="none", turns=turns, end_state=end or EndState()
    )


def graded(scn: Scenario, turns: list[TurnView], system: str = "p", end: EndState | None = None) -> CaseGrade:
    return grade(scn, transcript(turns, system, end), build_world())


def result(scn: Scenario, grade_: CaseGrade | None, system: str = "p", run_index: int = 1,
           segment: str = "basic", latency: int = 10) -> CaseResult:  # fmt: skip
    return CaseResult(
        run_id="fixture-run",
        system=system,
        run_index=run_index,
        model_label="none",
        scenario_id=scn.id,
        split=scn.split.value,
        workflow=scn.workflow.value if scn.workflow else None,
        category=scn.category.value,
        language=scn.language.value,
        dialect=scn.dialect.value,
        segment=segment,
        tags=list(scn.tags),
        in_scope=scn.in_scope,
        expected_outcome=scn.expected_outcome.value,
        mode=scn.mode.value,
        driver="scripted",
        review_status=scn.review_status.value,
        transcript=transcript([turn(latency_ms=latency)], system),
        grade=grade_,
        latency_ms=latency,
    )
