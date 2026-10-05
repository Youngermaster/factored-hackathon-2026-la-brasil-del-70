"""The ``account_inquiry`` definition: states, transitions, handlers, tools, and binding states.

Read only: there is no EXECUTE state and no write tool on any allowlist. Documented in
``docs/workflows/account-inquiry.md``.
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
from bank_agent.application.workflows.account_inquiry.answers import balances, payment_status
from bank_agent.application.workflows.account_inquiry.data import load, open_questions
from bank_agent.application.workflows.account_inquiry.follow_up import follow_up
from bank_agent.application.workflows.account_inquiry.payments import locate_payment
from bank_agent.application.workflows.account_inquiry.select import clarify, select_product
from bank_agent.application.workflows.account_inquiry.statement import statement_period, statement_summary
from bank_agent.application.workflows.account_inquiry.understand import understand
from bank_agent.application.workflows.account_inquiry.unsupported import recognize
from bank_agent.domain.actions import ToolName
from bank_agent.domain.workflow import WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG

T = ToolName
PRODUCTS = frozenset({T.LIST_MY_BALANCES, T.LIST_MY_CARDS})
PAYMENTS = PRODUCTS | {T.LIST_RECENT_TRANSACTIONS, T.GET_TRANSACTION}

STATES = (
    StateSpec(START, "START", accept_request, StateKind.ACCEPTS_REQUEST),
    auth_required_state(),
    StateSpec("UNDERSTAND", "START", understand, StateKind.WORKING),
    StateSpec("SELECT_PRODUCT", "IDENTIFY_PRODUCT", select_product, StateKind.WORKING, PRODUCTS),
    StateSpec("CLARIFY", "IDENTIFY_PRODUCT", clarify, StateKind.AWAITS_ANSWER, PAYMENTS),
    StateSpec("BALANCES", "ANSWER_BALANCE", balances, StateKind.ACCEPTS_REQUEST, frozenset({T.LIST_MY_BALANCES}),
              holds_context=True),
    StateSpec("LOCATE_PAYMENT", "ANSWER_PAYMENT_STATUS", locate_payment, StateKind.WORKING, PAYMENTS),
    StateSpec("PAYMENT_STATUS", "ANSWER_PAYMENT_STATUS", payment_status, StateKind.ACCEPTS_REQUEST,
              frozenset({T.GET_PAYMENT_STATUS, T.GET_TRANSACTION}), holds_context=True),
    StateSpec("STATEMENT_PERIOD", "ANSWER_STATEMENT", statement_period, StateKind.AWAITS_ANSWER),
    StateSpec("STATEMENT_SUMMARY", "ANSWER_STATEMENT", statement_summary, StateKind.ACCEPTS_REQUEST,
              PRODUCTS | {T.GET_STATEMENT_SUMMARY}, holds_context=True),
    end_state(RESOLVED),
    end_state(ABSTAINED),
    end_state(REFUSED),
    escalated_state(),
)  # fmt: skip

TRANSITIONS = {
    START: ("UNDERSTAND",),
    "UNDERSTAND": ("BALANCES", "LOCATE_PAYMENT", "SELECT_PRODUCT"),
    "SELECT_PRODUCT": ("CLARIFY", "STATEMENT_PERIOD", RESOLVED),
    "CLARIFY": ("SELECT_PRODUCT", "STATEMENT_PERIOD", "LOCATE_PAYMENT", "PAYMENT_STATUS"),
    "BALANCES": ("UNDERSTAND", RESOLVED),
    "LOCATE_PAYMENT": ("PAYMENT_STATUS", "CLARIFY"),
    "PAYMENT_STATUS": ("UNDERSTAND", "LOCATE_PAYMENT"),
    "STATEMENT_PERIOD": ("STATEMENT_SUMMARY",),
    "STATEMENT_SUMMARY": ("UNDERSTAND", "SELECT_PRODUCT"),
    RESOLVED: ("UNDERSTAND",),
    ABSTAINED: ("UNDERSTAND",),
    REFUSED: ("UNDERSTAND",),
}


def questions(ctx: TurnContext) -> tuple[str, ...]:
    return open_questions(load(ctx))


def build_account_inquiry() -> WorkflowDefinition:
    return build_definition(
        workflow=WorkflowId.ACCOUNT_INQUIRY,
        version=1,
        states=STATES,
        transitions=TRANSITIONS,
        intents=frozenset(WORKFLOW_CATALOG.descriptor(WorkflowId.ACCOUNT_INQUIRY).intents),
        open_questions=questions,
        unsupported=recognize,
        follow_up=follow_up,
    )
