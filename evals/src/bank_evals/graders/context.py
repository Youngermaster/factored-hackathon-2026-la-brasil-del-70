"""What every grader reads: the scenario, the transcript, and the case's world before the conversation."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

from bank_agent.domain.customer import Customer
from bank_evals.graders.model import Finding, UnsafeEvent, UnsafeType
from bank_evals.scenarios.model import Scenario
from bank_evals.systems.base import Transcript, TurnView
from bank_evals.world.fixtures import apply_fixtures
from bank_evals.world.model import World


@dataclass
class GradeContext:
    scenario: Scenario
    transcript: Transcript
    world: World
    """The case's world with the record fixtures applied, before any turn."""
    findings: list[Finding] = field(default_factory=list)
    unsafe: list[UnsafeEvent] = field(default_factory=list)

    @classmethod
    def build(cls, scenario: Scenario, transcript: Transcript, base: World) -> GradeContext:
        return cls(scenario, transcript, apply_fixtures(scenario, base.copy()))

    @cached_property
    def customer(self) -> Customer:
        return self.world.persona(self.scenario.persona_ref).customer

    @property
    def turns(self) -> list[TurnView]:
        return self.transcript.turns

    @cached_property
    def assistant_text(self) -> str:
        return "\n".join(turn.assistant_text for turn in self.turns)

    @cached_property
    def other_customers(self) -> list[Customer]:
        return [c for c in self.world.customers if c.customer_id != self.customer.customer_id]

    def resolve(self, ref: str) -> str:
        return self.world.resolve(self.scenario.persona_ref, ref)

    def fail(self, grader: str, code: str, detail: str = "") -> None:
        self.findings.append(Finding(grader=grader, code=code, detail=detail[:300]))

    def flag_unsafe(self, kind: UnsafeType, code: str, detail: str = "") -> None:
        if not any(event.type == kind and event.code == code for event in self.unsafe):
            self.unsafe.append(UnsafeEvent(type=kind, code=code, detail=detail[:300]))
        self.fail("safety", code, detail)

    @cached_property
    def pre_existing_cases(self) -> set[str]:
        return {case.case_id for case in self.world.cases}

    @cached_property
    def pre_existing_applications(self) -> set[str]:
        return {item.application_id for item in self.world.credit_applications}
