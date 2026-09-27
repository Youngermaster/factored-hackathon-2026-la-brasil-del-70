"""STATUS_INQUIRY: read-only answers from ``list_my_cases`` and ``get_case_status`` with the SLA and next steps;
an open case past its SLA escalates through ``DSP.case_within_sla``."""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.decide import evaluate
from bank_agent.application.engine.definition import RESOLVED
from bank_agent.application.engine.reply import Choices, Param, Reply
from bank_agent.application.engine.security import referenced_ids
from bank_agent.application.engine.shared import blocking_step, clause_ref
from bank_agent.application.engine.templates.labels import CASE_STATUSES
from bank_agent.domain.dispute import DisputeCase
from bank_agent.domain.identifiers import CaseId, SourceRef, SourceTable
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Outcome
from bank_agent.policy.facts import DisputeFacts

MAX_LISTED = 5


def _params(ctx: TurnContext, case: DisputeCase) -> dict[str, Param]:
    language = Language.ES if ctx.language is Language.EN else ctx.language
    return {
        "case": case.case_id,
        "amount": case.disputed_amount,
        "status": CASE_STATUSES[case.status][language],
        "due": case.sla_due_at.astimezone(ctx.zone).date(),
    }


async def status_inquiry(ctx: TurnContext) -> Step:
    named = referenced_ids(ctx.text).cases
    cases: list[DisputeCase] = []
    if named:
        found = await ctx.tools.get_case_status(CaseId(named[0]))
        cases = [found] if found is not None else []
    if not cases:
        listed = await ctx.tools.list_my_cases()
        cases = sorted([c for c in listed if c.is_open] or list(listed), key=lambda c: c.opened_at, reverse=True)
    for case in cases[:MAX_LISTED]:
        ctx.engine = ctx.engine.with_fact(
            f"case {case.case_id} is {case.status} with SLA {case.sla_due_at.date()}",
            SourceRef.of(SourceTable.DISPUTE_CASES, case.case_id),
        )
    breached = next((case for case in cases if case.is_open and case.sla_due_at < ctx.now), None)
    decision = evaluate(ctx, dispute=DisputeFacts(case_sla_breached=breached is not None))
    stop = blocking_step(ctx, decision, state="STATUS_INQUIRY")
    if stop is not None:
        return stop
    explain = (clause_ref(ctx, f"DSP-{ctx.customer.country.value}-2"), clause_ref(ctx, "INF-ALL-1"))
    if not cases:
        return Step(RESOLVED, Reply(template="dispute.status_none"), Outcome.RESOLVED)
    if len(cases) == 1:
        reply = Reply(template="dispute.status_one", params=_params(ctx, cases[0]), explain=explain)
        return Step(RESOLVED, reply, Outcome.RESOLVED)
    items = tuple(_params(ctx, case) for case in cases[:MAX_LISTED])
    reply = Reply(
        template="dispute.status_many", params={"items": Choices("dispute.status_item", items)}, explain=explain
    )
    return Step(RESOLVED, reply, Outcome.RESOLVED)
