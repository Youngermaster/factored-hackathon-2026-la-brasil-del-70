"""``/v1/conversations``: open a conversation, send turns, read the history and the customer's glass box.

One set of endpoints serves all four workflows; the router inside the engine picks the workflow per turn. Another
customer's conversation id is a 404 with the same body as an unknown id (one scoped query either way).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, status

from bank_agent.api.config import RateClass
from bank_agent.api.dependencies import endpoint, role_dependency, services
from bank_agent.api.schemas.conversations import (
    AssistantMessage,
    ConversationHistoryResponse,
    ConversationView,
    SendTurnRequest,
    TurnResponse,
    TurnView,
)
from bank_agent.api.schemas.trace import CustomerTraceRecord, CustomerTraceResponse
from bank_agent.domain.access import Role
from bank_agent.domain.conversation import Conversation, Turn, TurnResult
from bank_agent.domain.identifiers import ID_PATTERN, ConversationId, TurnId
from bank_agent.domain.session import Session

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])
CUSTOMER = frozenset({Role.CUSTOMER})
CustomerSession = Annotated[Session, Depends(role_dependency(CUSTOMER))]
ConversationPath = Annotated[ConversationId, Path(max_length=64, pattern=ID_PATTERN)]


def conversation_view(conversation: Conversation) -> ConversationView:
    return ConversationView(
        conversation_id=conversation.conversation_id,
        status=conversation.status,
        language=conversation.language,
        workflow=conversation.position.workflow,
        state=conversation.position.state,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def turn_response(result: TurnResult) -> TurnResponse:
    return TurnResponse(
        turn_id=result.turn_id,
        conversation_id=result.conversation_id,
        workflow=result.workflow,
        state=result.state,
        outcome=result.outcome,
        replayed=result.replayed,
        message=AssistantMessage.model_validate(result.response),
    )


def turn_view(turn: Turn) -> TurnView:
    return TurnView(
        turn_id=turn.turn_id,
        sequence=turn.sequence,
        received_at=turn.received_at,
        customer_text=turn.customer_text,
        language=turn.language,
        message=AssistantMessage.model_validate(turn.response) if turn.response is not None else None,
        completed_at=turn.completed_at,
    )


_CONVERSATIONS_CREATE = endpoint(
    rate=RateClass.WRITE, roles=CUSTOMER, changes_state=True, operation_id="conversations_create"
)


@router.post("", response_model=ConversationView, status_code=status.HTTP_201_CREATED, **_CONVERSATIONS_CREATE)
async def create_conversation(request: Request, session: CustomerSession) -> ConversationView:
    """Open an empty conversation for the signed-in customer."""
    return conversation_view(await services(request).conversations.open(session))


_CONVERSATIONS_SEND_TURN = endpoint(
    rate=RateClass.WRITE, roles=CUSTOMER, changes_state=True, operation_id="conversations_send_turn"
)


@router.post("/{conversation_id}/turns", response_model=TurnResponse, **_CONVERSATIONS_SEND_TURN)
async def send_turn(
    request: Request, conversation_id: ConversationPath, body: SendTurnRequest, session: CustomerSession
) -> TurnResponse:
    """Send one customer message and get the assistant's reply with every workflow part."""
    result = await services(request).conversations.send(session, conversation_id, TurnId(str(body.turn_id)), body.text)
    return turn_response(result)


_CONVERSATIONS_GET = endpoint(
    rate=RateClass.READ, roles=CUSTOMER, changes_state=False, operation_id="conversations_get"
)


@router.get("/{conversation_id}", response_model=ConversationHistoryResponse, **_CONVERSATIONS_GET)
async def get_conversation(
    request: Request, conversation_id: ConversationPath, session: CustomerSession
) -> ConversationHistoryResponse:
    """The conversation and its turns, oldest first."""
    history = await services(request).conversations.history(session, conversation_id)
    return ConversationHistoryResponse(
        conversation=conversation_view(history.conversation), turns=tuple(turn_view(t) for t in history.turns)
    )


_CONVERSATIONS_TRACE = endpoint(
    rate=RateClass.READ, roles=CUSTOMER, changes_state=False, operation_id="conversations_trace"
)


@router.get("/{conversation_id}/trace", response_model=CustomerTraceResponse, **_CONVERSATIONS_TRACE)
async def get_trace(
    request: Request, conversation_id: ConversationPath, session: CustomerSession
) -> CustomerTraceResponse:
    """The execution records of the customer's own conversation (glass box), without risk estimate values."""
    records = await services(request).conversations.trace(session, conversation_id)
    return CustomerTraceResponse(
        conversation_id=conversation_id, records=tuple(CustomerTraceRecord.of(record) for record in records)
    )
