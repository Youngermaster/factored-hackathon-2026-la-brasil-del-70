"""The ``credit`` definition: states, transitions, handlers, tools, and binding states.

The three credit components stay apart: conversation handling (UNDERSTAND, PRODUCT_INFO, CLARIFY,
COLLECT_APPLICATION_FACTS, EXPLAIN_ELIGIBILITY, the templates), the risk estimate (ESTIMATE_RISK, through the
``RiskEstimator`` port), and eligibility policy (ASSESS_ELIGIBILITY, through the ``EligibilityPolicy`` port). The
estimator, the eligibility service, and the credit profile read are engine calls, on no state's tool allowlist.
Documented in ``docs/workflows/credit-information.md``.
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
from bank_agent.application.workflows.credit.assessment import assess_step, estimate_step
from bank_agent.application.workflows.credit.collect import collect
from bank_agent.application.workflows.credit.data import load, open_questions
from bank_agent.application.workflows.credit.explain import explain
from bank_agent.application.workflows.credit.info import clarify, product_info
from bank_agent.application.workflows.credit.intake import confirm_intake, execute, verify
from bank_agent.application.workflows.credit.status import application_status
from bank_agent.application.workflows.credit.understand import understand
from bank_agent.application.workflows.credit.unsupported import recognize
from bank_agent.domain.actions import ActionKind, ToolName
from bank_agent.domain.workflow import WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG

T = ToolName
CATALOG = frozenset({T.LIST_CREDIT_PRODUCTS, T.GET_CREDIT_PRODUCT})
SUBMIT = {ActionKind.SUBMIT_CREDIT_APPLICATION: "SUBMIT_APPLICATION"}

STATES = (
    StateSpec(START, "START", accept_request, StateKind.ACCEPTS_REQUEST),
    auth_required_state(),
    StateSpec("UNDERSTAND", "START", understand, StateKind.WORKING),
    StateSpec("PRODUCT_INFO", "PRODUCT_DETAIL", product_info, StateKind.ACCEPTS_REQUEST, CATALOG),
    StateSpec("CLARIFY", "COLLECT_APPLICATION", clarify, StateKind.AWAITS_ANSWER, CATALOG),
    StateSpec("COLLECT_APPLICATION_FACTS", "COLLECT_APPLICATION", collect, StateKind.AWAITS_ANSWER, CATALOG),
    StateSpec("ESTIMATE_RISK", "COLLECT_APPLICATION", estimate_step, StateKind.WORKING, CATALOG),
    StateSpec("ASSESS_ELIGIBILITY", "PRESENT_ELIGIBILITY", assess_step, StateKind.WORKING, CATALOG),
    StateSpec("EXPLAIN_ELIGIBILITY", "PRESENT_ELIGIBILITY", explain, StateKind.AWAITS_ANSWER, CATALOG),
    StateSpec("CONFIRM_INTAKE", "CONFIRM_APPLICATION", confirm_intake, StateKind.AWAITS_ANSWER, CATALOG,
              resume_state="CONFIRM_INTAKE"),
    StateSpec("EXECUTE", "SUBMIT_APPLICATION", execute, StateKind.WORKING, CATALOG | {T.SUBMIT_CREDIT_APPLICATION},
              SUBMIT, resume_state="CONFIRM_INTAKE"),
    StateSpec("VERIFY", "SUBMIT_APPLICATION", verify, StateKind.WORKING, CATALOG, SUBMIT,
              resume_state="CONFIRM_INTAKE"),
    StateSpec("APPLICATION_STATUS", "ANSWER_APPLICATION_STATUS", application_status, StateKind.WORKING,
              CATALOG | {T.GET_CREDIT_APPLICATION_STATUS}),
    end_state(RESOLVED),
    end_state(ABSTAINED),
    end_state(REFUSED),
    escalated_state(),
)  # fmt: skip

TRANSITIONS = {
    START: ("UNDERSTAND",),
    "UNDERSTAND": ("PRODUCT_INFO", "COLLECT_APPLICATION_FACTS", "APPLICATION_STATUS", "CLARIFY"),
    "PRODUCT_INFO": ("COLLECT_APPLICATION_FACTS", "UNDERSTAND", "CLARIFY"),
    "CLARIFY": ("PRODUCT_INFO", "COLLECT_APPLICATION_FACTS"),
    "COLLECT_APPLICATION_FACTS": ("ESTIMATE_RISK", "CLARIFY", "PRODUCT_INFO"),
    "ESTIMATE_RISK": ("ASSESS_ELIGIBILITY", "COLLECT_APPLICATION_FACTS"),
    "ASSESS_ELIGIBILITY": ("EXPLAIN_ELIGIBILITY", "COLLECT_APPLICATION_FACTS"),
    "EXPLAIN_ELIGIBILITY": ("CONFIRM_INTAKE", "COLLECT_APPLICATION_FACTS", RESOLVED),
    "CONFIRM_INTAKE": ("EXECUTE", RESOLVED, "COLLECT_APPLICATION_FACTS"),
    "EXECUTE": ("VERIFY", "CONFIRM_INTAKE"),
    "VERIFY": (RESOLVED, "CONFIRM_INTAKE"),
    "APPLICATION_STATUS": (RESOLVED,),
    RESOLVED: ("UNDERSTAND",),
    ABSTAINED: ("UNDERSTAND",),
    REFUSED: ("UNDERSTAND",),
}


def questions(ctx: TurnContext) -> tuple[str, ...]:
    return open_questions(load(ctx))


def build_credit() -> WorkflowDefinition:
    return build_definition(
        workflow=WorkflowId.CREDIT,
        version=1,
        states=STATES,
        transitions=TRANSITIONS,
        intents=frozenset(WORKFLOW_CATALOG.descriptor(WorkflowId.CREDIT).intents),
        open_questions=questions,
        unsupported=recognize,
    )
