"""The ``dispute`` definition: states, transitions, handlers, tools, and binding states.

Documented in ``docs/workflows/dispute-intake.md``.
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
from bank_agent.application.workflows.dispute.act import execute, verify
from bank_agent.application.workflows.dispute.data import load, open_questions
from bank_agent.application.workflows.dispute.decide import (
    check_eligibility,
    classify_reason,
    confirm_summary,
    offer_block,
)
from bank_agent.application.workflows.dispute.locate import clarify, locate
from bank_agent.application.workflows.dispute.status import status_inquiry
from bank_agent.application.workflows.dispute.understand import understand
from bank_agent.domain.actions import ActionKind, ToolName
from bank_agent.domain.workflow import WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG

T = ToolName
LOOKUP = frozenset({T.LIST_RECENT_TRANSACTIONS, T.GET_TRANSACTION, T.GET_PRODUCT_STATUS, T.LIST_MY_CARDS})
DETAILS = frozenset({T.GET_TRANSACTION, T.GET_PRODUCT_STATUS, T.LIST_MY_CASES})
WRITE_STATES = {ActionKind.CREATE_DISPUTE_CASE: "CREATE_CASE", ActionKind.BLOCK_CARD: "EXECUTE_BLOCK"}

STATES = (
    StateSpec(START, "START", accept_request, StateKind.ACCEPTS_REQUEST),
    auth_required_state(),
    StateSpec("UNDERSTAND", "START", understand, StateKind.WORKING),
    StateSpec("STATUS_INQUIRY", "ANSWER_CASE_STATUS", status_inquiry, StateKind.WORKING,
              frozenset({T.LIST_MY_CASES, T.GET_CASE_STATUS})),
    StateSpec("LOCATE_TRANSACTION", "LOCATE_TRANSACTION", locate, StateKind.WORKING, LOOKUP),
    StateSpec("CLARIFY", "LOCATE_TRANSACTION", clarify, StateKind.AWAITS_ANSWER, LOOKUP),
    StateSpec("CHECK_ELIGIBILITY", "COLLECT_DETAILS", check_eligibility, StateKind.WORKING, DETAILS),
    StateSpec("CLASSIFY_REASON", "COLLECT_DETAILS", classify_reason, StateKind.AWAITS_ANSWER, DETAILS),
    StateSpec("OFFER_PROTECTIVE_BLOCK", "OFFER_CARD_BLOCK", offer_block, StateKind.AWAITS_ANSWER, DETAILS),
    StateSpec("CONFIRM_SUMMARY", "CONFIRM_DISPUTE", confirm_summary, StateKind.AWAITS_ANSWER, DETAILS,
              resume_state="CONFIRM_SUMMARY"),
    StateSpec("EXECUTE", "CREATE_CASE", execute, StateKind.WORKING,
              DETAILS | {T.CREATE_DISPUTE_CASE, T.BLOCK_CARD}, WRITE_STATES, resume_state="CONFIRM_SUMMARY"),
    StateSpec("VERIFY", "CREATE_CASE", verify, StateKind.WORKING, DETAILS | {T.GET_CASE_STATUS}, WRITE_STATES,
              resume_state="CONFIRM_SUMMARY"),
    end_state(RESOLVED),
    end_state(ABSTAINED),
    end_state(REFUSED),
    escalated_state(),
)  # fmt: skip

TRANSITIONS = {
    START: ("UNDERSTAND",),
    "UNDERSTAND": ("STATUS_INQUIRY", "LOCATE_TRANSACTION", "CLARIFY"),
    "STATUS_INQUIRY": (RESOLVED,),
    "LOCATE_TRANSACTION": ("CHECK_ELIGIBILITY", "CLARIFY"),
    "CLARIFY": ("LOCATE_TRANSACTION", "CHECK_ELIGIBILITY"),
    "CHECK_ELIGIBILITY": ("CLASSIFY_REASON", "LOCATE_TRANSACTION"),
    "CLASSIFY_REASON": ("OFFER_PROTECTIVE_BLOCK", "CONFIRM_SUMMARY", "LOCATE_TRANSACTION"),
    "OFFER_PROTECTIVE_BLOCK": ("CONFIRM_SUMMARY",),
    "CONFIRM_SUMMARY": ("EXECUTE", RESOLVED, "LOCATE_TRANSACTION"),
    "EXECUTE": ("VERIFY", "CONFIRM_SUMMARY"),
    "VERIFY": (RESOLVED, "CONFIRM_SUMMARY"),
    RESOLVED: ("UNDERSTAND",),
    ABSTAINED: ("UNDERSTAND",),
    REFUSED: ("UNDERSTAND",),
}


def questions(ctx: TurnContext) -> tuple[str, ...]:
    return open_questions(load(ctx))


def build_dispute() -> WorkflowDefinition:
    return build_definition(
        workflow=WorkflowId.DISPUTE,
        version=1,
        states=STATES,
        transitions=TRANSITIONS,
        intents=frozenset(WORKFLOW_CATALOG.descriptor(WorkflowId.DISPUTE).intents),
        open_questions=questions,
    )
