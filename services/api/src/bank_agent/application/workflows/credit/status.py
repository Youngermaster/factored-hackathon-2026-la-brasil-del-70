"""APPLICATION_STATUS: the status of the customer's application intakes, read only.

The application comes from an id the customer names (the engine has already checked that it is theirs; another
customer's id is refused before this state runs) or from an intake verified earlier in this conversation. Without
either, ``list_my_credit_applications`` reads the session customer's intakes: one answers its status, several list
the newest ``MAX_LISTED`` with product, date, and status (no follow-up question, since every listed status is
already answered), and none says there is no application on record and offers the catalog. Statuses have no
approved or declined value by design.
"""

from collections.abc import Mapping

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.reply import Choices, Param, Reply
from bank_agent.application.engine.security import referenced_ids
from bank_agent.application.engine.shared import clause_ref
from bank_agent.application.engine.templates.labels import APPLICATION_STATUSES, CREDIT_TYPES, pick
from bank_agent.domain.actions import ActionKind
from bank_agent.domain.credit import CreditApplicationIntake, CreditProduct
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.identifiers import ApplicationId, CreditProductCode, SourceRef, SourceTable
from bank_agent.domain.workflow import Outcome

RESOLVED = "RESOLVED"
MAX_LISTED = 3


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


def _params(
    ctx: TurnContext, intake: CreditApplicationIntake, catalog: Mapping[CreditProductCode, CreditProduct]
) -> dict[str, Param]:
    """Template parameters for one intake; records the status as a verified fact with its evidence."""
    product = catalog.get(intake.product_code)
    kind = pick(CREDIT_TYPES[product.product_type], ctx.language) if product is not None else intake.product_code
    evidence = SourceRef.of(SourceTable.CREDIT_APPLICATIONS, intake.application_id)
    ctx.engine = ctx.engine.with_fact(f"application {intake.application_id} is {intake.status.value}", evidence)
    return {
        "application": intake.application_id,
        "name": kind,
        "status": pick(APPLICATION_STATUSES[intake.status], ctx.language),
    }


async def _intakes(ctx: TurnContext) -> list[CreditApplicationIntake] | None:
    """The intakes to answer about, newest first; ``None`` when a named or verified id is not found."""
    application_id = _known(ctx)
    if application_id is None:
        return list(await ctx.tools.list_my_credit_applications())
    intake = await ctx.tools.get_credit_application_status(application_id)
    return [intake] if intake is not None else None


async def application_status(ctx: TurnContext) -> Step:
    explain: tuple[ClauseRef, ...] = (clause_ref(ctx, "INF-ALL-3"),)
    intakes = await _intakes(ctx)
    if intakes is None:
        return Step(RESOLVED, Reply(template="credit.status_not_found"), Outcome.RESOLVED)
    if not intakes:
        return Step(RESOLVED, Reply(template="credit.status_none_on_record", explain=explain), Outcome.RESOLVED)
    catalog = {p.product_code: p for p in await ctx.tools.list_credit_products()}
    explain = (*explain, clause_ref(ctx, "CRE-ALL-1"))
    if len(intakes) == 1:
        reply = Reply(template="credit.application_status", params=_params(ctx, intakes[0], catalog), explain=explain)
        return Step(RESOLVED, reply, Outcome.RESOLVED)
    items = tuple(
        {**_params(ctx, intake, catalog), "created": intake.created_at.astimezone(ctx.zone).date()}
        for intake in intakes[:MAX_LISTED]
    )
    reply = Reply(
        template="credit.application_statuses",
        params={"items": Choices("credit.application_status_item", items)},
        explain=explain,
    )
    return Step(RESOLVED, reply, Outcome.RESOLVED)
