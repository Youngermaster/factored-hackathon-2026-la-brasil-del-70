"""The ``card_support`` definition: states, transitions, handlers, tools, and binding states.

Documented in ``docs/workflows/card-support.md``.
"""

from bank_agent.application.engine.context import TurnContext
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
from bank_agent.application.engine.states import accept_request, auth_required_state, end_state, escalated_state
from bank_agent.application.workflows.card_support.block import confirm_block, execute, verify
from bank_agent.application.workflows.card_support.data import load
from bank_agent.application.workflows.card_support.follow_up import follow_up
from bank_agent.application.workflows.card_support.select import WHICH_CARD, clarify, select_card, understand
from bank_agent.application.workflows.card_support.status import card_status
from bank_agent.domain.actions import ActionKind, ToolName
from bank_agent.domain.workflow import WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG

T = ToolName
CARDS = frozenset({T.LIST_MY_CARDS, T.GET_PRODUCT_STATUS})
BLOCK = {ActionKind.BLOCK_CARD: "EXECUTE_BLOCK"}

STATES = (
    StateSpec(START, "START", accept_request, StateKind.ACCEPTS_REQUEST),
    auth_required_state(),
    StateSpec("UNDERSTAND", "START", understand, StateKind.WORKING),
    StateSpec("SELECT_CARD", "IDENTIFY_CARD", select_card, StateKind.WORKING, CARDS),
    StateSpec("CLARIFY", "IDENTIFY_CARD", clarify, StateKind.AWAITS_ANSWER, CARDS),
    StateSpec("CARD_STATUS", "ANSWER_CARD_STATUS", card_status, StateKind.ACCEPTS_REQUEST,
              CARDS | {T.LIST_RECENT_TRANSACTIONS}, holds_context=True),
    StateSpec("CONFIRM_BLOCK", "CONFIRM_BLOCK", confirm_block, StateKind.AWAITS_ANSWER, CARDS,
              resume_state="CONFIRM_BLOCK"),
    StateSpec("EXECUTE", "EXECUTE_BLOCK", execute, StateKind.WORKING, CARDS | {T.BLOCK_CARD}, BLOCK,
              resume_state="CONFIRM_BLOCK"),
    StateSpec("VERIFY", "EXECUTE_BLOCK", verify, StateKind.WORKING, CARDS, BLOCK, resume_state="CONFIRM_BLOCK"),
    end_state(RESOLVED),
    end_state(ABSTAINED),
    end_state(REFUSED),
    escalated_state(),
)  # fmt: skip

TRANSITIONS = {
    START: ("UNDERSTAND",),
    "UNDERSTAND": ("SELECT_CARD",),
    "SELECT_CARD": ("CLARIFY", "CARD_STATUS", "CONFIRM_BLOCK", RESOLVED),
    "CLARIFY": ("SELECT_CARD", "CARD_STATUS", "CONFIRM_BLOCK"),
    "CARD_STATUS": ("CONFIRM_BLOCK", "SELECT_CARD", "UNDERSTAND"),
    "CONFIRM_BLOCK": ("EXECUTE", RESOLVED),
    "EXECUTE": ("VERIFY", "CONFIRM_BLOCK"),
    "VERIFY": (RESOLVED, "CONFIRM_BLOCK"),
    RESOLVED: ("UNDERSTAND",),
    ABSTAINED: ("UNDERSTAND",),
    REFUSED: ("UNDERSTAND",),
}


def questions(ctx: TurnContext) -> tuple[str, ...]:
    return WHICH_CARD if load(ctx).product_id is None else ()


def build_card_support() -> WorkflowDefinition:
    return build_definition(
        workflow=WorkflowId.CARD_SUPPORT,
        version=1,
        states=STATES,
        transitions=TRANSITIONS,
        intents=frozenset(WORKFLOW_CATALOG.descriptor(WorkflowId.CARD_SUPPORT).intents),
        open_questions=questions,
        follow_up=follow_up,
    )
