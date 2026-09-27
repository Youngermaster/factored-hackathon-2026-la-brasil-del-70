"""The ``credit_review`` section of a credit handoff: what was assessed, why a person is needed, and the estimate.

The estimate is not kept between turns, so it is derived again here, deterministically, from the same profile and
application facts (and recorded in this turn's execution record). Agents see it in the handoff; customers never do.
"""

from bank_agent.application.engine.context import TurnContext
from bank_agent.application.workflows.credit.assessment import application_facts, estimate_in_turn, turn_estimate
from bank_agent.application.workflows.credit.data import CreditData
from bank_agent.application.workflows.credit.info import product_of
from bank_agent.domain.eligibility import CreditReview, EligibilityAssessment, ReviewReason


async def credit_review(
    ctx: TurnContext,
    data: CreditData,
    assessment: EligibilityAssessment,
    *,
    extra: tuple[ReviewReason, ...] = (),
) -> CreditReview:
    product = await product_of(ctx, data.product_type) if data.product_type is not None else None
    application = application_facts(data, product) if product is not None else None
    if product is not None and application is not None and "risk_estimate" not in ctx.turn_values:
        await estimate_in_turn(ctx, product, application)
    return CreditReview.from_assessment(assessment, estimate=turn_estimate(ctx), extra_reasons=extra)
