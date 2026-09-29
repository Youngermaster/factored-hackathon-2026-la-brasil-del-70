"""Database end-state assertions (``expected_state_assertions``) against the case's end state."""

from __future__ import annotations

from typing import Any

from bank_evals.graders.context import GradeContext
from bank_evals.graders.lexicon import eligibility_from_text
from bank_evals.scenarios.model import (
    CaseCount,
    CaseExists,
    CreditApplicationCount,
    CreditApplicationExists,
    EligibilityOutcomeIs,
    HandoffExists,
    NoWrites,
    ProductStatusIs,
    StateAssertion,
)

GRADER = "state"


def new_cases(ctx: GradeContext) -> list[dict[str, Any]]:
    return [c for c in ctx.transcript.end_state.cases if c["case_id"] not in ctx.pre_existing_cases]


def new_applications(ctx: GradeContext) -> list[dict[str, Any]]:
    apps = ctx.transcript.end_state.applications
    return [a for a in apps if a["application_id"] not in ctx.pre_existing_applications]


def observed_eligibility(ctx: GradeContext) -> str | None:
    """The last eligibility outcome shown: the structured view (P), or the words of the reply (B1)."""
    for turn in reversed(ctx.turns):
        if turn.eligibility_outcome is not None:
            return turn.eligibility_outcome
    if ctx.transcript.system == "b1":
        for turn in reversed(ctx.turns):
            found = eligibility_from_text(turn.assistant_text)
            if found is not None:
                return found
    return None


def _handoff_codes(ctx: GradeContext) -> list[str]:
    codes = []
    for item in ctx.transcript.end_state.handoffs:
        document = item["document"]
        reason = document.get("escalation_reason")
        codes.append(reason.get("code", "") if isinstance(reason, dict) else str(reason or ""))
    return codes


def holds(ctx: GradeContext, assertion: StateAssertion) -> bool:
    end = ctx.transcript.end_state
    if isinstance(assertion, CaseExists):
        target = ctx.resolve(assertion.transaction_ref)
        return any(
            c["transaction_id"] == target
            and (assertion.reason is None or c["reason"] == assertion.reason.value)
            and (assertion.status is None or c["status"] == assertion.status.value)
            for c in end.cases
        )
    if isinstance(assertion, CaseCount):
        return len(new_cases(ctx)) == assertion.count
    if isinstance(assertion, ProductStatusIs):
        return end.product_statuses.get(ctx.resolve(assertion.product_ref)) == assertion.status.value
    if isinstance(assertion, HandoffExists):
        codes = _handoff_codes(ctx)
        return bool(codes) and (
            assertion.reason_code is None or ctx.transcript.system == "b1" or assertion.reason_code.value in codes
        )
    if isinstance(assertion, NoWrites):
        return end.writes == 0
    if isinstance(assertion, CreditApplicationExists):
        return any(
            (assertion.product_code is None or a["product_code"] == assertion.product_code)
            and (assertion.status is None or a["status"] == assertion.status.value)
            for a in end.applications
        )
    if isinstance(assertion, CreditApplicationCount):
        return len(new_applications(ctx)) == assertion.count
    if isinstance(assertion, EligibilityOutcomeIs):
        return observed_eligibility(ctx) == assertion.outcome.value
    raise TypeError(f"unknown assertion {type(assertion).__name__}")


def check_state(ctx: GradeContext) -> bool:
    ok = True
    for assertion in ctx.scenario.expected_state_assertions:
        if not holds(ctx, assertion):
            ok = False
            ctx.fail(GRADER, f"assertion_{assertion.kind}", assertion.model_dump_json())
    return ok


def expected_writes(ctx: GradeContext) -> int:
    """Writes the scenario expects: new cases, blocked cards, and new applications it asserts."""
    count = 0
    for assertion in ctx.scenario.expected_state_assertions:
        if isinstance(assertion, CaseExists) and assertion.status is None:
            count += 1
        elif isinstance(assertion, ProductStatusIs) and assertion.status.value == "blocked":
            product = ctx.world.product(ctx.resolve(assertion.product_ref))
            count += int(product.status.value != "blocked")
        elif isinstance(assertion, CreditApplicationExists):
            count += 1
    return count
