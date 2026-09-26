"""The workflow registry as pure data: which workflow owns which intents, and what each may do.

``WORKFLOW_CATALOG`` describes the four supported workflows (CLAUDE.md section 1). The router uses it to
dispatch an intent and to move a conversation between workflows; the workflow engine (phase 09) builds its
state machines keyed by it. An intent that no workflow owns and that is not cross-workflow is out of scope.

This module sits above ``workflow``, ``actions``, and ``policy`` because a descriptor references action kinds
and clause families, which themselves import the workflow vocabulary.
"""

from collections import Counter
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Self

from pydantic import Field, PositiveInt, model_validator

from bank_agent.domain.actions import ActionKind
from bank_agent.domain.base import DomainModel
from bank_agent.domain.cards import ESCALATION_ONLY_CARD_ACTIONS, SELF_SERVICE_CARD_ACTIONS, CardAction
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.policy import ClauseFamily
from bank_agent.domain.workflow import CROSS_WORKFLOW_INTENTS, Intent, StateName, WorkflowId


class WorkflowDescriptor(DomainModel):
    """One workflow: the intents it owns, where it starts, the clause families it binds, and what it may do.

    ``write_actions`` are the only actions the workflow may perform (together with the per-state allowlist in
    the policy matrix). ``escalation_only_intents`` are owned intents that always end in a handoff, with no tool.
    """

    id: WorkflowId
    version: PositiveInt
    intents: Annotated[tuple[Intent, ...], Field(min_length=1)]
    entry_state: StateName
    clause_families: Annotated[tuple[ClauseFamily, ...], Field(min_length=1)]
    write_actions: tuple[ActionKind, ...] = ()
    escalation_only_intents: tuple[Intent, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> Self:
        for name, values in (
            ("intents", self.intents),
            ("clause_families", self.clause_families),
            ("write_actions", self.write_actions),
            ("escalation_only_intents", self.escalation_only_intents),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must not repeat a value")
        if CROSS_WORKFLOW_INTENTS & set(self.intents):
            raise ValueError("a workflow cannot own a cross-workflow intent")
        if not set(self.escalation_only_intents) <= set(self.intents):
            raise ValueError("escalation-only intents must be intents the workflow owns")
        return self


class WorkflowCatalog(DomainModel):
    """A validated set of workflow descriptors: unique ids, and every owned intent owned by exactly one."""

    descriptors: Annotated[tuple[WorkflowDescriptor, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _validate(self) -> Self:
        ids = Counter(descriptor.id for descriptor in self.descriptors)
        if any(count > 1 for count in ids.values()):
            raise ValueError("a workflow id can appear only once in a catalog")
        owners = Counter(intent for descriptor in self.descriptors for intent in descriptor.intents)
        if any(count > 1 for count in owners.values()):
            raise ValueError("an intent can be owned by only one workflow")
        return self

    def ids(self) -> tuple[WorkflowId, ...]:
        return tuple(descriptor.id for descriptor in self.descriptors)

    def descriptor(self, workflow: WorkflowId) -> WorkflowDescriptor:
        """Return the descriptor of ``workflow``; ``KeyError`` when the catalog does not contain it."""
        for descriptor in self.descriptors:
            if descriptor.id is workflow:
                return descriptor
        raise KeyError(workflow.value)

    def workflow_for(self, intent: Intent) -> WorkflowId | None:
        """The workflow that owns ``intent``, or ``None`` for a cross-workflow or unowned intent."""
        for descriptor in self.descriptors:
            if intent in descriptor.intents:
                return descriptor.id
        return None

    def unowned_intents(self) -> frozenset[Intent]:
        """Intents that are neither owned by a workflow in this catalog nor cross-workflow."""
        owned = {intent for descriptor in self.descriptors for intent in descriptor.intents}
        return frozenset(Intent) - owned - CROSS_WORKFLOW_INTENTS


_COMMON_FAMILIES = (ClauseFamily.SCOPE, ClauseFamily.AUTH, ClauseFamily.PRV)

WORKFLOW_CATALOG = WorkflowCatalog(
    descriptors=(
        WorkflowDescriptor(
            id=WorkflowId.ACCOUNT_INQUIRY,
            version=1,
            intents=(Intent.BALANCE_INQUIRY, Intent.PAYMENT_STATUS, Intent.STATEMENT_REQUEST),
            entry_state="START",
            clause_families=(*_COMMON_FAMILIES, ClauseFamily.ACC, ClauseFamily.ESC),
        ),
        WorkflowDescriptor(
            id=WorkflowId.CARD_SUPPORT,
            version=1,
            intents=(
                Intent.CARD_STATUS,
                Intent.CARD_BLOCK,
                Intent.CARD_UNBLOCK_REQUEST,
                Intent.CARD_REPLACEMENT_REQUEST,
            ),
            entry_state="START",
            clause_families=(*_COMMON_FAMILIES, ClauseFamily.CRD, ClauseFamily.ESC),
            write_actions=(ActionKind.BLOCK_CARD,),
            escalation_only_intents=(Intent.CARD_UNBLOCK_REQUEST, Intent.CARD_REPLACEMENT_REQUEST),
        ),
        WorkflowDescriptor(
            id=WorkflowId.DISPUTE,
            version=1,
            intents=(Intent.DISPUTE_NEW, Intent.DISPUTE_STATUS),
            entry_state="START",
            clause_families=(*_COMMON_FAMILIES, ClauseFamily.DSP, ClauseFamily.CRD, ClauseFamily.ESC),
            write_actions=(ActionKind.CREATE_DISPUTE_CASE, ActionKind.BLOCK_CARD),
        ),
        WorkflowDescriptor(
            id=WorkflowId.CREDIT,
            version=1,
            intents=(
                Intent.CREDIT_PRODUCT_INFO,
                Intent.CREDIT_ELIGIBILITY,
                Intent.CREDIT_APPLICATION,
                Intent.CREDIT_APPLICATION_STATUS,
            ),
            entry_state="START",
            clause_families=(*_COMMON_FAMILIES, ClauseFamily.CRE, ClauseFamily.ELG, ClauseFamily.ESC),
        ),
    )
)
"""The four supported workflows. The credit workflow gains ``submit_credit_application`` with that action."""


class CardActionHandlingKind(StrEnum):
    SELF_SERVICE = "self_service"
    ESCALATION_ONLY = "escalation_only"


class CardActionHandling(DomainModel):
    """How the system handles one card action.

    A self-service action runs through its write action with confirmation, step-up, and a verified read-back.
    An escalation-only action has no tool: the request goes to a human with ``escalation_code``.
    """

    action: CardAction
    kind: CardActionHandlingKind
    write_action: ActionKind | None = None
    escalation_code: EscalationReasonCode | None = None
    requires_confirmation: bool
    requires_step_up: bool
    verified_read_back: bool
    workflows: Annotated[tuple[WorkflowId, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.kind is CardActionHandlingKind.SELF_SERVICE:
            if self.action not in SELF_SERVICE_CARD_ACTIONS or self.write_action is None:
                raise ValueError("a self-service card action needs a write action")
            if self.escalation_code is not None:
                raise ValueError("a self-service card action has no escalation code")
            if not (self.requires_confirmation and self.requires_step_up and self.verified_read_back):
                raise ValueError("a card write needs confirmation, step-up, and a verified read-back")
        else:
            if self.action not in ESCALATION_ONLY_CARD_ACTIONS or self.escalation_code is None:
                raise ValueError("an escalation-only card action needs an escalation code")
            if self.write_action is not None or self.requires_confirmation or self.verified_read_back:
                raise ValueError("an escalation-only card action has no tool, confirmation, or read-back")
        return self


CARD_ACTION_HANDLING: Mapping[CardAction, CardActionHandling] = MappingProxyType(
    {
        CardAction.BLOCK: CardActionHandling(
            action=CardAction.BLOCK,
            kind=CardActionHandlingKind.SELF_SERVICE,
            write_action=ActionKind.BLOCK_CARD,
            requires_confirmation=True,
            requires_step_up=True,
            verified_read_back=True,
            workflows=(WorkflowId.CARD_SUPPORT, WorkflowId.DISPUTE),
        ),
        CardAction.UNBLOCK_REQUEST: CardActionHandling(
            action=CardAction.UNBLOCK_REQUEST,
            kind=CardActionHandlingKind.ESCALATION_ONLY,
            escalation_code=EscalationReasonCode.CARD_UNBLOCK_REQUESTED,
            requires_confirmation=False,
            requires_step_up=False,
            verified_read_back=False,
            workflows=(WorkflowId.CARD_SUPPORT,),
        ),
        CardAction.REPLACEMENT_REQUEST: CardActionHandling(
            action=CardAction.REPLACEMENT_REQUEST,
            kind=CardActionHandlingKind.ESCALATION_ONLY,
            escalation_code=EscalationReasonCode.CARD_REPLACEMENT_REQUESTED,
            requires_confirmation=False,
            requires_step_up=False,
            verified_read_back=False,
            workflows=(WorkflowId.CARD_SUPPORT,),
        ),
    }
)
"""Every ``CardAction`` and how it is handled. A test checks that the table covers every action."""
