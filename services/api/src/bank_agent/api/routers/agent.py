"""``/v1/agent``: the handoff inbox (list, read, claim, resolve) and credit application intakes (read, review, close).

Agents act on structured handoffs; they never read a customer's conversation. Claims, resolutions, and credit review
moves are audited.
Every handoff view carries its policy basis with the clause excerpts rendered from the loaded pack.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import AwareDatetime

from bank_agent.api.config import RateClass
from bank_agent.api.dependencies import endpoint, role_dependency, services
from bank_agent.api.schemas.agent import (
    CreditApplicationListResponse,
    CreditApplicationMoveRequest,
    CreditApplicationView,
    HandoffListResponse,
    HandoffView,
    ResolveHandoffRequest,
)
from bank_agent.domain.access import Role
from bank_agent.domain.complaint import Priority
from bank_agent.domain.credit import ApplicationStatus
from bank_agent.domain.escalation import EscalationReasonCode
from bank_agent.domain.handoff import HandoffStatus
from bank_agent.domain.identifiers import ID_PATTERN, ApplicationId, HandoffId
from bank_agent.domain.locale import Language
from bank_agent.domain.session import Session
from bank_agent.domain.workflow import WorkflowId
from bank_agent.ports.repositories.handoffs import HandoffQuery

router = APIRouter(prefix="/v1/agent", tags=["agent"])
AGENT = frozenset({Role.AGENT})
AgentSession = Annotated[Session, Depends(role_dependency(AGENT))]
HandoffPath = Annotated[HandoffId, Path(max_length=64, pattern=ID_PATTERN)]
ApplicationPath = Annotated[ApplicationId, Path(max_length=64, pattern=ID_PATTERN)]


_AGENT_LIST_HANDOFFS = endpoint(
    rate=RateClass.READ, roles=AGENT, changes_state=False, operation_id="agent_list_handoffs"
)


@router.get("/handoffs", response_model=HandoffListResponse, **_AGENT_LIST_HANDOFFS)
async def list_handoffs(
    request: Request,
    session: AgentSession,
    workflow: Annotated[list[WorkflowId] | None, Query(max_length=4)] = None,
    priority: Annotated[list[Priority] | None, Query(max_length=4)] = None,
    reason: Annotated[list[EscalationReasonCode] | None, Query(max_length=20)] = None,
    language: Annotated[list[Language] | None, Query(max_length=3)] = None,
    status: Annotated[list[HandoffStatus] | None, Query(max_length=3)] = None,
    sla_due_before: Annotated[AwareDatetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> HandoffListResponse:
    """The inbox, soonest SLA first, filtered by workflow, priority, reason, language, status, and SLA due."""
    query = HandoffQuery.model_validate(
        {
            "workflows": tuple(workflow or ()),
            "priorities": tuple(priority or ()),
            "reasons": tuple(reason or ()),
            "languages": tuple(language or ()),
            "statuses": tuple(status or ()),
            "sla_due_before": sla_due_before,
            "limit": limit,
        }
    )
    provider = services(request)
    records = await provider.inbox.list(session, query)
    return HandoffListResponse(handoffs=tuple(HandoffView.of(record, provider.policy_clauses) for record in records))


_AGENT_GET_HANDOFF = endpoint(rate=RateClass.READ, roles=AGENT, changes_state=False, operation_id="agent_get_handoff")


@router.get("/handoffs/{handoff_id}", response_model=HandoffView, **_AGENT_GET_HANDOFF)
async def get_handoff(request: Request, handoff_id: HandoffPath, session: AgentSession) -> HandoffView:
    provider = services(request)
    return HandoffView.of(await provider.inbox.get(session, handoff_id), provider.policy_clauses)


_AGENT_CLAIM_HANDOFF = endpoint(
    rate=RateClass.WRITE, roles=AGENT, changes_state=True, operation_id="agent_claim_handoff"
)


@router.post("/handoffs/{handoff_id}/claim", response_model=HandoffView, **_AGENT_CLAIM_HANDOFF)
async def claim_handoff(request: Request, handoff_id: HandoffPath, session: AgentSession) -> HandoffView:
    """Claim an open handoff for the signed-in agent."""
    provider = services(request)
    return HandoffView.of(await provider.inbox.claim(session, handoff_id), provider.policy_clauses)


_AGENT_RESOLVE_HANDOFF = endpoint(
    rate=RateClass.WRITE, roles=AGENT, changes_state=True, operation_id="agent_resolve_handoff"
)


@router.post("/handoffs/{handoff_id}/resolve", response_model=HandoffView, **_AGENT_RESOLVE_HANDOFF)
async def resolve_handoff(
    request: Request, handoff_id: HandoffPath, body: ResolveHandoffRequest, session: AgentSession
) -> HandoffView:
    """Resolve a handoff this agent claimed, with an outcome code and a note."""
    provider = services(request)
    record = await provider.inbox.resolve(session, handoff_id, body.outcome, body.note)
    return HandoffView.of(record, provider.policy_clauses)


_AGENT_LIST_CREDIT_APPLICATIONS = endpoint(
    rate=RateClass.READ, roles=AGENT, changes_state=False, operation_id="agent_list_credit_applications"
)


@router.get("/credit-applications", response_model=CreditApplicationListResponse, **_AGENT_LIST_CREDIT_APPLICATIONS)
async def list_credit_applications(
    request: Request,
    session: AgentSession,
    status: Annotated[list[ApplicationStatus] | None, Query(max_length=4)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> CreditApplicationListResponse:
    """Reviewable intakes (submitted, under human review) and any a handoff references, newest first.

    Read only, and never a lending decision.
    """
    statuses = frozenset(status) if status else None
    applications = await services(request).inbox.credit_applications(session, statuses, limit)
    return CreditApplicationListResponse(
        applications=tuple(CreditApplicationView.model_validate(item) for item in applications)
    )


_AGENT_GET_CREDIT_APPLICATION = endpoint(
    rate=RateClass.READ, roles=AGENT, changes_state=False, operation_id="agent_get_credit_application"
)


@router.get(
    "/credit-applications/{application_id}", response_model=CreditApplicationView, **_AGENT_GET_CREDIT_APPLICATION
)
async def get_credit_application(
    request: Request, application_id: ApplicationPath, session: AgentSession
) -> CreditApplicationView:
    return CreditApplicationView.model_validate(
        await services(request).inbox.credit_application(session, application_id)
    )


_AGENT_REVIEW_CREDIT_APPLICATION = endpoint(
    rate=RateClass.WRITE, roles=AGENT, changes_state=True, operation_id="agent_review_credit_application"
)


@router.post(
    "/credit-applications/{application_id}/review",
    response_model=CreditApplicationView,
    **_AGENT_REVIEW_CREDIT_APPLICATION,
)
async def review_credit_application(
    request: Request, application_id: ApplicationPath, body: CreditApplicationMoveRequest, session: AgentSession
) -> CreditApplicationView:
    """Take a submitted intake into human review. Audited; never a lending decision."""
    moved = await services(request).inbox.review_credit_application(session, application_id, body.expected_version)
    return CreditApplicationView.model_validate(moved)


_AGENT_CLOSE_CREDIT_APPLICATION = endpoint(
    rate=RateClass.WRITE, roles=AGENT, changes_state=True, operation_id="agent_close_credit_application"
)


@router.post(
    "/credit-applications/{application_id}/close",
    response_model=CreditApplicationView,
    **_AGENT_CLOSE_CREDIT_APPLICATION,
)
async def close_credit_application(
    request: Request, application_id: ApplicationPath, body: CreditApplicationMoveRequest, session: AgentSession
) -> CreditApplicationView:
    """Close an intake under human review. Audited; there is no approved or declined status."""
    moved = await services(request).inbox.close_credit_application(session, application_id, body.expected_version)
    return CreditApplicationView.model_validate(moved)
