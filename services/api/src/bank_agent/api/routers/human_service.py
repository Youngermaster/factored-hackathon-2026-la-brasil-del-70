"""Real human service in the customer's existing conversation, authorized by the claimed handoff."""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from bank_agent.api.config import RateClass
from bank_agent.api.dependencies import endpoint, services
from bank_agent.api.routers.agent import AgentSession, HandoffPath
from bank_agent.api.routers.conversations import ConversationPath, CustomerSession
from bank_agent.api.schemas.human_service import HumanMessageResponse, HumanServiceResponse, SendHumanMessageRequest
from bank_agent.domain.access import Role

router = APIRouter(tags=["human-service"])
Cursor = Annotated[int, Query(ge=0, le=2147483647)]

_CUSTOMER_HISTORY = endpoint(
    rate=RateClass.READ,
    roles=frozenset({Role.CUSTOMER}),
    changes_state=False,
    operation_id="conversations_human_service",
)


@router.get(
    "/v1/conversations/{conversation_id}/human-service", response_model=HumanServiceResponse, **_CUSTOMER_HISTORY
)
async def customer_history(
    request: Request, conversation_id: ConversationPath, session: CustomerSession, after: Cursor = 0
) -> HumanServiceResponse:
    view = await services(request).human_service.customer_history(session, conversation_id, after)
    return HumanServiceResponse.model_validate(view)


_CUSTOMER_SEND = endpoint(
    rate=RateClass.WRITE,
    roles=frozenset({Role.CUSTOMER}),
    changes_state=True,
    operation_id="conversations_send_human_message",
)


@router.post(
    "/v1/conversations/{conversation_id}/human-service/messages", response_model=HumanMessageResponse, **_CUSTOMER_SEND
)
async def customer_send(
    request: Request, conversation_id: ConversationPath, body: SendHumanMessageRequest, session: CustomerSession
) -> HumanMessageResponse:
    receipt = await services(request).human_service.send_customer(
        session, conversation_id, str(body.message_id), body.text
    )
    return HumanMessageResponse.model_validate(receipt)


_AGENT_HISTORY = endpoint(
    rate=RateClass.READ,
    roles=frozenset({Role.AGENT}),
    changes_state=False,
    operation_id="agent_human_service",
)


@router.get("/v1/agent/handoffs/{handoff_id}/human-service", response_model=HumanServiceResponse, **_AGENT_HISTORY)
async def agent_history(
    request: Request, handoff_id: HandoffPath, session: AgentSession, after: Cursor = 0
) -> HumanServiceResponse:
    view = await services(request).human_service.agent_history(session, handoff_id, after)
    return HumanServiceResponse.model_validate(view)


_AGENT_SEND = endpoint(
    rate=RateClass.WRITE,
    roles=frozenset({Role.AGENT}),
    changes_state=True,
    operation_id="agent_send_human_message",
)


@router.post(
    "/v1/agent/handoffs/{handoff_id}/human-service/messages", response_model=HumanMessageResponse, **_AGENT_SEND
)
async def agent_send(
    request: Request, handoff_id: HandoffPath, body: SendHumanMessageRequest, session: AgentSession
) -> HumanMessageResponse:
    receipt = await services(request).human_service.send_agent(session, handoff_id, str(body.message_id), body.text)
    return HumanMessageResponse.model_validate(receipt)
