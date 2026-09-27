"""B0 credit: the catalog is shown, and every eligibility, application, or status question goes to a person.

No risk estimator, no eligibility service, and no intake: B0 is the menu-and-rules bot the proposed system is
compared with in phase 14.
"""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.definition import (
    ABSTAINED,
    REFUSED,
    RESOLVED,
    START,
    StateKind,
    StateSpec,
    WorkflowDefinition,
    build_definition,
)
from bank_agent.application.engine.shared import abstain_unsupported, escalate
from bank_agent.application.engine.states import accept_request, auth_required_state, end_state, escalated_state
from bank_agent.application.workflows.credit.data import CreditData, load, open_questions, save
from bank_agent.application.workflows.credit.definition import CATALOG
from bank_agent.application.workflows.credit.info import _listing, detail
from bank_agent.application.workflows.credit.understand import absorb
from bank_agent.application.workflows.credit.unsupported import recognize
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.workflow import Intent, WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG

VARIANT = "baseline_b0"


async def understand(ctx: TurnContext) -> Step:
    request = recognize(ctx.text)
    if request is not None:
        return abstain_unsupported(ctx, request)
    routed = ctx.prediction.intent if ctx.prediction is not None else None
    if routed not in (None, Intent.CREDIT_PRODUCT_INFO):
        return escalate(ctx, EscalationReasonCode.UNSUPPORTED_NEEDS_HUMAN, "baseline_b0_credit",
                        open_questions=("What does the customer ask about credit?",))  # fmt: skip
    data = await absorb(ctx, CreditData(intent=Intent.CREDIT_PRODUCT_INFO), ctx.text, use_model=False)
    save(ctx, data)
    return Step("PRODUCT_INFO")


async def product_info(ctx: TurnContext) -> Step:
    data = load(ctx)
    if (data.listed or data.detailed) and not ctx.reprompt:
        return Step("UNDERSTAND")
    if data.product_type is None:
        return await _listing(ctx, data)
    return await detail(ctx, data, data.product_type)


def _questions(ctx: TurnContext) -> tuple[str, ...]:
    return open_questions(load(ctx))


def build_credit_b0() -> WorkflowDefinition:
    states = (
        StateSpec(START, "START", accept_request, StateKind.ACCEPTS_REQUEST),
        auth_required_state(),
        StateSpec("UNDERSTAND", "START", understand, StateKind.WORKING),
        StateSpec("PRODUCT_INFO", "PRODUCT_DETAIL", product_info, StateKind.ACCEPTS_REQUEST, CATALOG),
        end_state(RESOLVED),
        end_state(ABSTAINED),
        end_state(REFUSED),
        escalated_state(),
    )
    transitions = {
        START: ("UNDERSTAND",),
        "UNDERSTAND": ("PRODUCT_INFO",),
        "PRODUCT_INFO": ("UNDERSTAND",),
        RESOLVED: ("UNDERSTAND",),
        ABSTAINED: ("UNDERSTAND",),
        REFUSED: ("UNDERSTAND",),
    }
    return build_definition(
        workflow=WorkflowId.CREDIT,
        version=1,
        states=states,
        transitions=transitions,
        intents=frozenset(WORKFLOW_CATALOG.descriptor(WorkflowId.CREDIT).intents),
        variant=VARIANT,
        open_questions=_questions,
        unsupported=recognize,
    )
