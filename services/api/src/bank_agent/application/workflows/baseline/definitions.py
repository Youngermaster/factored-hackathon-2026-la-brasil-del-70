"""B0 definitions: the proposed tables with the understanding, location, and reason states replaced and no
protective block offer. Registered as the ``baseline_b0`` registry (``bootstrap/workflows.py``)."""

from collections.abc import Callable, Mapping
from dataclasses import replace

from bank_agent.application.engine.definition import WorkflowDefinition, build_definition
from bank_agent.application.workflows.account_inquiry import definition as account
from bank_agent.application.workflows.account_inquiry.unsupported import recognize
from bank_agent.application.workflows.baseline import account as account_b0
from bank_agent.application.workflows.baseline import handlers
from bank_agent.application.workflows.baseline import templates as _templates
from bank_agent.application.workflows.card_support import definition as card
from bank_agent.application.workflows.dispute import definition as dispute
from bank_agent.domain.workflow import WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG

VARIANT = "baseline_b0"
_REPLACED = {
    "UNDERSTAND": handlers.understand,
    "LOCATE_TRANSACTION": handlers.locate,
    "CLASSIFY_REASON": handlers.classify_reason,
}
del _templates


def build_dispute_b0() -> WorkflowDefinition:
    states = tuple(
        replace(spec, handler=_REPLACED[spec.name]) if spec.name in _REPLACED else spec
        for spec in dispute.STATES
        if spec.name != "OFFER_PROTECTIVE_BLOCK"
    )
    transitions = {
        name: tuple(t for t in targets if t != "OFFER_PROTECTIVE_BLOCK")
        for name, targets in dispute.TRANSITIONS.items()
        if name != "OFFER_PROTECTIVE_BLOCK"
    }
    return build_definition(
        workflow=WorkflowId.DISPUTE,
        version=1,
        states=states,
        transitions=transitions,
        intents=frozenset(WORKFLOW_CATALOG.descriptor(WorkflowId.DISPUTE).intents),
        variant=VARIANT,
        open_questions=dispute.questions,
    )


def build_card_support_b0() -> WorkflowDefinition:
    return build_definition(
        workflow=WorkflowId.CARD_SUPPORT,
        version=1,
        states=card.STATES,
        transitions=card.TRANSITIONS,
        intents=frozenset(WORKFLOW_CATALOG.descriptor(WorkflowId.CARD_SUPPORT).intents),
        variant=VARIANT,
        open_questions=card.questions,
    )


def build_account_inquiry_b0() -> WorkflowDefinition:
    replaced = {"UNDERSTAND": account_b0.understand, "LOCATE_PAYMENT": account_b0.locate_payment}
    return build_definition(
        workflow=WorkflowId.ACCOUNT_INQUIRY,
        version=1,
        states=tuple(replace(s, handler=replaced[s.name]) if s.name in replaced else s for s in account.STATES),
        transitions=account.TRANSITIONS,
        intents=frozenset(WORKFLOW_CATALOG.descriptor(WorkflowId.ACCOUNT_INQUIRY).intents),
        variant=VARIANT,
        open_questions=account.questions,
        unsupported=recognize,
    )


BASELINE_DEFINITIONS: Mapping[WorkflowId, Callable[[], WorkflowDefinition]] = {
    WorkflowId.ACCOUNT_INQUIRY: build_account_inquiry_b0,
    WorkflowId.DISPUTE: build_dispute_b0,
    WorkflowId.CARD_SUPPORT: build_card_support_b0,
}
