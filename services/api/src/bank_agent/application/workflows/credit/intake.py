"""CONFIRM_INTAKE, EXECUTE, and VERIFY: an application intake recorded for human review, never a decision.

Only after an explanation, and only for ``indicatively_eligible`` (the offer) or ``review_required`` (an explicit
request). CONFIRM_INTAKE shows the product, the amount, the term (loans), the purpose, and that a person reviews the
application and nothing is decided in the conversation. EXECUTE needs step-up (the policy matrix) and calls
``submit_credit_application`` with an idempotency key from the conversation, the assessment, the product, and the
action, and links the intake to that assessment and conversation; VERIFY reads it back, and only a positive
read-back is reported as recorded.
"""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.decide import beyond_step_up, evaluate, explanation
from bank_agent.application.engine.idempotency import derive_key
from bank_agent.application.engine.reply import CreditEvidence, Param, Reply
from bank_agent.application.engine.shared import abstain, blocking_step, clause_ref, spend_clarification
from bank_agent.application.engine.templates.labels import PURPOSES, pick
from bank_agent.application.understanding.answers import YesNo, parse_yes_no
from bank_agent.application.workflows.credit.assessment import application_facts
from bank_agent.application.workflows.credit.data import CreditData, load, open_questions, save
from bank_agent.application.workflows.credit.info import facts, name, product_of
from bank_agent.application.workflows.shared.writes import PlannedWrite, ReadBack, execute_writes, verify_writes
from bank_agent.domain.actions import ActionKind, ActionRequest, SubmitCreditApplicationArguments, ToolName
from bank_agent.domain.conversation import ActionDisplayStatus, ActionStatusView, CreditIntakeConfirmation
from bank_agent.domain.credit import CreditProduct, CreditProductType
from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.eligibility import EligibilityOutcome
from bank_agent.domain.errors import InvariantViolationError
from bank_agent.domain.identifiers import ApplicationId, SourceRef, SourceTable
from bank_agent.domain.workflow import Outcome
from bank_agent.policy.facts import CreditFacts

CONFIRM, EXECUTE, VERIFY = "CONFIRM_INTAKE", "EXECUTE", "VERIFY"
ALLOWED = frozenset({EligibilityOutcome.INDICATIVELY_ELIGIBLE, EligibilityOutcome.REVIEW_REQUIRED})
DENIED = "credit.intake_not_possible"


def intake_request(
    ctx: TurnContext, data: CreditData, product: CreditProduct, *, confirmed: bool, state: str
) -> ActionRequest | None:
    application = application_facts(data, product)
    if application is None or data.assessment is None:
        return None
    target = SourceRef.of(SourceTable.CREDIT_PRODUCTS, product.product_code)
    scope = f"{ctx.conversation.conversation_id}|{data.assessment.assessment_id}"
    return ActionRequest(
        action=ActionKind.SUBMIT_CREDIT_APPLICATION,
        target=target,
        arguments=SubmitCreditApplicationArguments(
            product_code=product.product_code,
            requested_amount=application.requested_amount,
            requested_term_months=application.requested_term_months,
            purpose=application.purpose,
            declared_monthly_income=application.declared_monthly_income,
            assessment_ref=data.assessment.assessment_id,
            origin_conversation_id=ctx.conversation.conversation_id,
        ),
        idempotency_key=derive_key(scope, target, ActionKind.SUBMIT_CREDIT_APPLICATION),
        requested_in_state=state,
        confirmed_at=ctx.now if confirmed else None,
    )


def arguments_of(request: ActionRequest) -> SubmitCreditApplicationArguments:
    arguments = request.arguments
    if not isinstance(arguments, SubmitCreditApplicationArguments):
        raise InvariantViolationError("an intake request carries intake arguments")
    return arguments


def _credit_facts(data: CreditData, product: CreditProduct) -> CreditFacts:
    outcome = data.assessment.outcome if data.assessment is not None else None
    return facts(product).evolve(eligibility_outcome=outcome)


def _confirm_reply(ctx: TurnContext, data: CreditData, product: CreditProduct, request: ActionRequest) -> Reply:
    arguments = arguments_of(request)
    params: dict[str, Param] = {
        "name": name(ctx, product.product_type),
        "amount": arguments.requested_amount,
        "purpose": pick(PURPOSES.get(arguments.purpose, PURPOSES["general_purpose"]), ctx.language),
    }
    suffix: tuple[tuple[str, dict[str, Param]], ...] = ()
    if product.product_type is not CreditProductType.CREDIT_CARD:
        suffix = (("credit.term_line", {"term": arguments.requested_term_months}),)
    return Reply(
        template="credit.confirm_intake",
        params=params,
        suffix=suffix,
        # INF-ALL-3 says the application "queda registrada": it is cited after the verified read-back, never before
        # the customer confirms (QA 2026-10-05, CRE-11).
        explain=(clause_ref(ctx, "CRE-ALL-1"),),
        credit=CreditEvidence(product=product, assessment=data.assessment),
        prefix="common.confirm_again" if data.intake_shown and not ctx.reprompt else None,
        credit_intake_confirmation=CreditIntakeConfirmation(
            product_code=product.product_code,
            product_type=product.product_type,
            requested_amount=arguments.requested_amount,
            requested_term_months=arguments.requested_term_months,
            purpose=arguments.purpose,
            eligibility_outcome=data.assessment.outcome if data.assessment is not None else None,
            planned_actions=(ActionKind.SUBMIT_CREDIT_APPLICATION,),
        ),
    )


async def confirm_intake(ctx: TurnContext) -> Step:
    data = load(ctx)
    product = await product_of(ctx, data.product_type) if data.product_type is not None else None
    if product is None or data.assessment is None or data.assessment.outcome not in ALLOWED:
        return abstain(ctx, DENIED, (clause_ref(ctx, "CRE-ALL-3"),))
    if data.intake_shown and not ctx.reprompt:
        answer = parse_yes_no(ctx.text)
        if answer is YesNo.YES:
            return Step(EXECUTE)
        if answer is YesNo.NO:
            save(ctx, data.evolve(intake_shown=False))
            return Step("RESOLVED", Reply(template="common.nothing_recorded"), Outcome.RESOLVED)
        stop = spend_clarification(ctx, open_questions=open_questions(data))
        if stop is not None:
            return stop
    request = intake_request(ctx, data, product, confirmed=False, state="CONFIRM_APPLICATION")
    if request is None:
        return Step("COLLECT_APPLICATION_FACTS")
    decision = evaluate(ctx, action=request, credit=_credit_facts(data, product))
    stop = blocking_step(ctx, decision, state=CONFIRM, step_up_ok=True)
    if stop is not None:
        return stop
    if beyond_step_up(decision) in (DecisionKind.DENY, DecisionKind.ABSTAIN):
        return abstain(ctx, DENIED, explanation(decision))
    reply = _confirm_reply(ctx, data, product, request)
    save(ctx, data.evolve(intake_shown=True))
    return Step(CONFIRM, reply, Outcome.IN_PROGRESS)


async def execute(ctx: TurnContext) -> Step:
    data = load(ctx)
    product = await product_of(ctx, data.product_type) if data.product_type is not None else None
    request = intake_request(ctx, data, product, confirmed=True, state="SUBMIT_APPLICATION") if product else None
    if product is None or request is None:
        return Step(CONFIRM)
    arguments = arguments_of(request)

    async def run() -> SourceRef:
        intake = await ctx.tools.submit_credit_application(arguments, request.idempotency_key)
        return SourceRef.of(SourceTable.CREDIT_APPLICATIONS, intake.application_id)

    write = PlannedWrite(
        request, "SUBMIT_APPLICATION", run, credit=_credit_facts(data, product), denied_template=DENIED
    )
    stop = await execute_writes(ctx, [write], state=EXECUTE)
    return stop or Step(VERIFY)


async def verify(ctx: TurnContext) -> Step:
    data = load(ctx)
    product = await product_of(ctx, data.product_type) if data.product_type is not None else None
    request = intake_request(ctx, data, product, confirmed=True, state="SUBMIT_APPLICATION") if product else None
    done = ctx.engine.executed_for(request.idempotency_key) if request is not None else None
    if request is None or done is None or done.outcome_ref is None:
        return Step(CONFIRM)
    arguments = arguments_of(request)
    application_id, verifier = ApplicationId(done.outcome_ref.key), ctx.write_verifier()
    check = ReadBack(
        ToolName.SUBMIT_CREDIT_APPLICATION,
        request.idempotency_key,
        lambda: verifier.credit_application_submitted(
            application_id,
            product_code=arguments.product_code,
            requested_amount=arguments.requested_amount,
            requested_term_months=arguments.requested_term_months,
        ),
    )
    stop = await verify_writes(ctx, [check])
    if stop is not None:
        return stop
    status = ActionStatusView(
        action=ActionKind.SUBMIT_CREDIT_APPLICATION, status=ActionDisplayStatus.VERIFIED, evidence=done.outcome_ref
    )
    save(ctx, data.evolve(intake_shown=False))
    reply = Reply(
        template="credit.intake_recorded",
        params={"application": application_id},
        explain=(clause_ref(ctx, "INF-ALL-3"),),
        action_statuses=(status,),
        credit=CreditEvidence(product=product, assessment=data.assessment),
    )
    return Step("RESOLVED", reply, Outcome.RESOLVED)
