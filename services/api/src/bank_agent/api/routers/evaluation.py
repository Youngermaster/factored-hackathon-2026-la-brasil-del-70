"""``/v1/eval``: published evaluation summaries and every conversation's execution records, for evaluators.

Summaries are offline measurements, per workflow and in aggregate. They are public read-only when
``EVAL_SUMMARIES_PUBLIC=true``; otherwise, like the traces, they need an evaluator session. The evaluator trace
includes the internal risk estimates (phase 02b rule).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request

from bank_agent.api.config import RateClass
from bank_agent.api.dependencies import endpoint, role_dependency, security_config, services
from bank_agent.api.schemas.evaluation import EvaluationSummariesResponse
from bank_agent.api.schemas.trace import StaffTraceRecord, StaffTraceResponse
from bank_agent.domain.access import Role
from bank_agent.domain.identifiers import ID_PATTERN, ConversationId
from bank_agent.domain.session import Session

router = APIRouter(prefix="/v1/eval", tags=["evaluation"])
EVALUATOR = frozenset({Role.EVALUATOR})
EvaluatorSession = Annotated[Session, Depends(role_dependency(EVALUATOR))]
ConversationPath = Annotated[ConversationId, Path(max_length=64, pattern=ID_PATTERN)]


async def evaluator_unless_public(request: Request) -> None:
    """Evaluator sessions only, unless the summaries are configured public."""
    if not security_config(request).eval_summaries_public:
        await role_dependency(EVALUATOR)(request)


evaluator_unless_public.roles = EVALUATOR  # type: ignore[attr-defined]


_EVAL_LIST_SUMMARIES = endpoint(
    rate=RateClass.READ,
    roles=None,
    changes_state=False,
    operation_id="eval_list_summaries",
    access=evaluator_unless_public,
    openapi_extra={"x-roles": ["evaluator"], "x-public-when": "EVAL_SUMMARIES_PUBLIC=true"},
)


@router.get("/summaries", response_model=EvaluationSummariesResponse, **_EVAL_LIST_SUMMARIES)
async def list_summaries(request: Request) -> EvaluationSummariesResponse:
    """Published evaluation summaries, newest first; empty until the harness publishes a run."""
    return EvaluationSummariesResponse(summaries=tuple(await services(request).evaluation_summaries.list()))


_EVAL_CONVERSATION_TRACE = endpoint(
    rate=RateClass.READ, roles=EVALUATOR, changes_state=False, operation_id="eval_conversation_trace"
)


@router.get("/conversations/{conversation_id}/trace", response_model=StaffTraceResponse, **_EVAL_CONVERSATION_TRACE)
async def conversation_trace(
    request: Request, conversation_id: ConversationPath, session: EvaluatorSession
) -> StaffTraceResponse:
    """Every execution record of any conversation, with the internal risk estimates."""
    records = await services(request).conversations.trace(session, conversation_id)
    return StaffTraceResponse(
        conversation_id=conversation_id, records=tuple(StaffTraceRecord.of(record) for record in records)
    )
