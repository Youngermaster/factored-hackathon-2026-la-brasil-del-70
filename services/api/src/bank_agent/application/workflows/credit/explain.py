"""EXPLAIN_ELIGIBILITY: the phase 06 rendering of ``EligibilityView`` and the review path the outcome allows.

The customer sees the outcome in plain words, each reason with its citation, the uncertainty statement, the review
path, and the ``CRE-ALL-1`` disclaimer; never the estimate or a profile value. ``indicatively_eligible`` offers an
intake for human review; ``review_required`` and ``insufficient_data`` offer a handoff with a ``credit_review``
section (``insufficient_data`` also accepts a declared income and assesses again); ``not_eligible`` offers a person.
A customer who contests the result is handed off with ``eligibility_contested``.
"""

import re

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.decide import evaluate
from bank_agent.application.engine.reply import CreditEvidence, Reply
from bank_agent.application.engine.shared import blocking_step, escalate, spend_clarification
from bank_agent.application.understanding.answers import YesNo, parse_yes_no
from bank_agent.application.understanding.text import fold
from bank_agent.application.workflows.credit.approval import answer_then_ask_again, asks_approval
from bank_agent.application.workflows.credit.assessment import turn_estimate, turn_profile
from bank_agent.application.workflows.credit.data import CreditData, Offer, load, open_questions, save
from bank_agent.application.workflows.credit.info import facts, product_of
from bank_agent.application.workflows.credit.review import credit_review
from bank_agent.application.workflows.credit.understand import absorb
from bank_agent.domain.credit import CreditProduct
from bank_agent.domain.decision import Decision, DecisionKind
from bank_agent.domain.eligibility import EligibilityAssessment, EligibilityOutcome, EligibilityView, ReviewReason
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.workflow import Outcome
from bank_agent.policy.eligibility import render_eligibility
from bank_agent.policy.eligibility.render import DISCLAIMER_CLAUSE
from bank_agent.policy.explain import render_body

EXPLAIN = "EXPLAIN_ELIGIBILITY"
OFFERS = {
    EligibilityOutcome.INDICATIVELY_ELIGIBLE: (Offer.INTAKE, "credit.offer_intake"),
    EligibilityOutcome.REVIEW_REQUIRED: (Offer.REVIEW_HANDOFF, "credit.offer_review"),
    EligibilityOutcome.INSUFFICIENT_DATA: (Offer.REVIEW_HANDOFF, "credit.offer_review"),
    EligibilityOutcome.NOT_ELIGIBLE: (Offer.CONTACT, "credit.offer_review"),
}
_CONTEST = re.compile(
    r"\bno estoy de acuerdo\b|\bno es justo\b|\bno me parece\b|\bapelar\b|\bimpugn|\bnao concordo\b|\bdiscordo\b|"
    r"\bnao e justo\b|\bcontest(o|ar) (el|o) resultado\b|\bresultado (esta |)(mal|errado|equivocado)\b|\bdisagree\b"
)
_RECORD = re.compile(
    r"\bregistr(?:a|ar|e|en|ame|e-me)\b.{0,20}\b(?:solicitud|solicitacao|pedido)\b|"
    r"\bregistr(?:ala|amela|ela|enla|arla|ame|e-a|a-la|ar-la)\b"
)
"""A request to record the intake ("regístrame la solicitud", "regístrala"; QA 2026-10-05, CRE-10)."""
_NEGATED = re.compile(r"^(?:no|nao)\b|\bno (?:la |lo |me )?registr|\bnao registr")
RECORDABLE = frozenset({EligibilityOutcome.INDICATIVELY_ELIGIBLE, EligibilityOutcome.REVIEW_REQUIRED})


def contests(text: str) -> bool:
    return bool(_CONTEST.search(fold(text)))


def question(assessment: EligibilityAssessment) -> tuple[Offer, str]:
    offer, template = OFFERS[assessment.outcome]
    if assessment.outcome is EligibilityOutcome.INSUFFICIENT_DATA and "monthly_income" in assessment.missing_facts:
        template = "credit.offer_missing_income"
    return offer, template


def eligibility_reply(ctx: TurnContext, assessment: EligibilityAssessment, product: CreditProduct) -> Reply:
    """The rendered view plus the review question. The verifier gets the assessment (claims must match) and the
    profile, estimate, and declared income as figures that must not appear; phrasing gets none of those three."""
    pack = ctx.services.policy.pack
    view = EligibilityView.from_assessment(assessment)
    rendered = render_eligibility(pack, view, ctx.language, ctx.locale)
    disclaimer = render_body(pack.get_clause(DISCLAIMER_CLAUSE, ctx.language), ctx.locale)
    _, template = question(assessment)
    reasons = tuple(line[2:] for line in rendered.text.split("\n") if line.startswith("- "))
    evidence = CreditEvidence(
        assessment=assessment,
        product=product,
        profile=turn_profile(ctx),
        estimate=turn_estimate(ctx),
        declared_income=load(ctx).declared_income,
        outcome=assessment.outcome.value,
        reasons=reasons,
        disclaimer=disclaimer,
    )
    return Reply(
        template="credit.eligibility",
        params={"explanation": rendered.text},
        suffix=((template, {}),),
        cite=rendered.citations,
        credit=evidence,
        eligibility=view,
    )


def _decision(
    ctx: TurnContext, data: CreditData, product: CreditProduct | None, *, contested: bool = False
) -> Decision:
    credit = facts(product).evolve(eligibility_outcome=data.assessment.outcome if data.assessment else None)
    return evaluate(ctx, policy_state="PRESENT_ELIGIBILITY", credit=credit, eligibility_contested=contested)


def _offered_only(decision: Decision) -> bool:
    """``ESC.credit_review_required`` alone: a review is offered, not forced."""
    return decision.kind is DecisionKind.ESCALATE and set(decision.decisive_rule_ids) == {"ESC.credit_review_required"}


def _ask_again(ctx: TurnContext, data: CreditData) -> Step:
    stop = spend_clarification(ctx, open_questions=open_questions(data))
    if stop is not None:
        return stop
    _, template = question(data.assessment) if data.assessment is not None else (Offer.NONE, "credit.offer_review")
    return Step(EXPLAIN, Reply(template=template, prefix="common.confirm_again"), Outcome.CLARIFIED, unanswered=True)


async def _review(ctx: TurnContext, data: CreditData, product: CreditProduct | None) -> Step:
    """The accepted review path: a handoff with a ``credit_review`` section."""
    assessment = data.assessment
    if assessment is None:
        return Step("COLLECT_APPLICATION_FACTS")
    decision = _decision(ctx, data, product)
    review = await credit_review(ctx, data, assessment)
    if assessment.outcome is EligibilityOutcome.NOT_ELIGIBLE:
        ctx.escalation = ctx.escalation.evolve(human_requested=True)
        return escalate(ctx, EscalationReasonCode.HUMAN_REQUESTED, "credit_review_requested", decision=decision,
                        credit_review=review)  # fmt: skip
    detail = f"credit_review_required: {assessment.outcome.value}"
    return escalate(ctx, EscalationReasonCode.CREDIT_REVIEW_REQUIRED, detail, decision=decision, credit_review=review)


async def explain(ctx: TurnContext) -> Step:
    data = load(ctx)
    assessment = data.assessment
    if assessment is None:
        return Step("COLLECT_APPLICATION_FACTS")
    product = await product_of(ctx, data.product_type) if data.product_type is not None else None
    if data.explained and not ctx.reprompt:
        return await _answer(ctx, data, product)
    if product is None:
        return Step("COLLECT_APPLICATION_FACTS")
    decision = _decision(ctx, data, product)
    if not _offered_only(decision):
        stop = blocking_step(ctx, decision, state=EXPLAIN)
        if stop is not None:
            return stop
    offer, _ = question(assessment)
    save(ctx, data.evolve(explained=True, offer=offer))
    settled = assessment.outcome in (EligibilityOutcome.INDICATIVELY_ELIGIBLE, EligibilityOutcome.NOT_ELIGIBLE)
    return Step(
        EXPLAIN, eligibility_reply(ctx, assessment, product), Outcome.RESOLVED if settled else Outcome.IN_PROGRESS
    )


async def _answer(ctx: TurnContext, data: CreditData, product: CreditProduct | None) -> Step:
    assessment = data.assessment
    if assessment is None:
        return Step("COLLECT_APPLICATION_FACTS")
    if contests(ctx.text):
        decision = _decision(ctx, data, product, contested=True)
        review = await credit_review(ctx, data, assessment, extra=(ReviewReason.CUSTOMER_CONTESTS_RESULT,))
        ctx.escalation = ctx.escalation.evolve(eligibility_contested=True)
        return escalate(ctx, EscalationReasonCode.ELIGIBILITY_CONTESTED, "eligibility_contested", decision=decision,
                        credit_review=review)  # fmt: skip
    if asks_approval(ctx.text):
        # "¿Me garantizan que lo aprueban?" after the view: no decision is made here; the offer is asked again.
        _, template = question(assessment)
        return answer_then_ask_again(ctx, Step(EXPLAIN, Reply(template=template), Outcome.CLARIFIED))
    updated = await absorb(ctx, data, ctx.text)
    keys = ("amount", "term_months", "declared_income", "product_type")
    if any(getattr(updated, key) != getattr(data, key) for key in keys):
        save(ctx, updated.evolve(assessment=None, explained=False, offer=Offer.NONE, product_code=None))
        return Step("COLLECT_APPLICATION_FACTS")
    if assessment.outcome in RECORDABLE and _RECORD.search(fold(ctx.text)) and not _NEGATED.search(fold(ctx.text)):
        save(ctx, data.evolve(intake_shown=False))
        return Step("CONFIRM_INTAKE")
    answer = parse_yes_no(ctx.text)
    if answer is YesNo.NO:
        save(ctx, data.evolve(offer=Offer.NONE))
        return Step("RESOLVED", Reply(template="common.nothing_recorded"), Outcome.RESOLVED)
    if answer is YesNo.UNCLEAR:
        return _ask_again(ctx, data)
    if data.offer is Offer.INTAKE:
        save(ctx, data.evolve(intake_shown=False))
        return Step("CONFIRM_INTAKE")
    return await _review(ctx, data, product)
