"""APPLICATION_STATUS: the status of an application intake, read only.

No tool lists a customer's applications, so the status comes from an intake verified in this conversation or an
application id the customer names (the engine has already checked that it is theirs; another customer's id is
refused before this state runs). Statuses have no approved or declined value by design.
"""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.reply import Param, Reply
from bank_agent.application.engine.security import referenced_ids
from bank_agent.application.engine.shared import clause_ref
from bank_agent.application.engine.templates.labels import APPLICATION_STATUSES, CREDIT_TYPES, pick
from bank_agent.domain.actions import ActionKind
from bank_agent.domain.identifiers import ApplicationId, SourceRef, SourceTable
from bank_agent.domain.workflow import Outcome

RESOLVED = "RESOLVED"


def _known(ctx: TurnContext) -> ApplicationId | None:
    named = referenced_ids(ctx.text).applications
    if named:
        return ApplicationId(named[0])
    submitted = [
        item.outcome_ref
        for item in ctx.engine.executed
        if item.action is ActionKind.SUBMIT_CREDIT_APPLICATION and item.verified and item.outcome_ref is not None
    ]
    return ApplicationId(submitted[-1].key) if submitted else None


async def application_status(ctx: TurnContext) -> Step:
    explain = (clause_ref(ctx, "INF-ALL-3"),)
    application_id = _known(ctx)
    if application_id is None:
        return Step(RESOLVED, Reply(template="credit.status_need_reference", explain=explain), Outcome.RESOLVED)
    intake = await ctx.tools.get_credit_application_status(application_id)
    if intake is None:
        return Step(RESOLVED, Reply(template="credit.status_not_found"), Outcome.RESOLVED)
    listed = {p.product_code: p for p in await ctx.tools.list_credit_products()}
    product = listed.get(intake.product_code)
    kind = pick(CREDIT_TYPES[product.product_type], ctx.language) if product is not None else intake.product_code
    evidence = SourceRef.of(SourceTable.CREDIT_APPLICATIONS, intake.application_id)
    ctx.engine = ctx.engine.with_fact(f"application {intake.application_id} is {intake.status.value}", evidence)
    params: dict[str, Param] = {
        "application": intake.application_id,
        "name": kind,
        "status": pick(APPLICATION_STATUSES[intake.status], ctx.language),
    }
    reply = Reply(template="credit.application_status", params=params, explain=(*explain, clause_ref(ctx, "CRE-ALL-1")))
    return Step(RESOLVED, reply, Outcome.RESOLVED)
