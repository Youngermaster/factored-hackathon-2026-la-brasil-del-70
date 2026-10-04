"""The real human message channel: customer follow-ups and replies from the agent who claimed the handoff."""

from bank_agent.domain.access import Role
from bank_agent.domain.audit import AuditEvent, AuditOutcome
from bank_agent.domain.errors import AccessContextError, ConversationNotFoundError, HandoffNotFoundError
from bank_agent.domain.handoff import HandoffRecord, HandoffStatus
from bank_agent.domain.human_service import HumanMessageReceipt, HumanServiceStatus, HumanServiceView
from bank_agent.domain.identifiers import AuditEventId, ConversationId, HandoffId, IdKind, SourceRef, SourceTable
from bank_agent.domain.session import Session
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

_STATUSES = {
    HandoffStatus.OPEN: HumanServiceStatus.QUEUED,
    HandoffStatus.CLAIMED: HumanServiceStatus.JOINED,
    HandoffStatus.RESOLVED: HumanServiceStatus.CLOSED,
}


class HumanService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, ids: IdGenerator) -> None:
        self._uow_factory, self._clock, self._ids = uow_factory, clock, ids

    async def _customer_record(self, uow: UnitOfWork, conversation_id: ConversationId) -> HandoffRecord:
        if await uow.conversations.get(conversation_id) is None:
            raise ConversationNotFoundError()
        record = await uow.human_service.for_conversation(conversation_id)
        if record is None:
            raise HandoffNotFoundError()
        return record

    async def _view(self, uow: UnitOfWork, record: HandoffRecord, after: int) -> HumanServiceView:
        return HumanServiceView(
            conversation_id=record.handoff.conversation_ref,
            handoff_id=HandoffId(record.handoff_id),
            status=_STATUSES[record.status],
            queued_at=record.handoff.created_at,
            joined_at=record.claimed_at,
            closed_at=record.resolution.resolved_at if record.resolution is not None else None,
            messages=tuple(await uow.human_service.messages(HandoffId(record.handoff_id), after=after)),
        )

    async def customer_history(
        self, session: Session, conversation_id: ConversationId, after: int = 0
    ) -> HumanServiceView:
        if session.role is not Role.CUSTOMER:
            raise AccessContextError("customer channel requires a customer session")
        async with self._uow_factory(session.access_context()) as uow:
            return await self._view(uow, await self._customer_record(uow, conversation_id), after)

    async def agent_history(self, session: Session, handoff_id: HandoffId, after: int = 0) -> HumanServiceView:
        if session.role is not Role.AGENT:
            raise AccessContextError("agent channel requires an agent session")
        async with self._uow_factory(session.access_context()) as uow:
            record = await uow.handoffs.get(handoff_id)
            if record is None or record.claimed_by != session.staff_id:
                raise HandoffNotFoundError()
            return await self._view(uow, record, after)

    async def send_customer(
        self, session: Session, conversation_id: ConversationId, message_id: str, text: str
    ) -> HumanMessageReceipt:
        if session.role is not Role.CUSTOMER:
            raise AccessContextError("customer channel requires a customer session")
        async with self._uow_factory(session.access_context()) as uow:
            record = await self._customer_record(uow, conversation_id)
            return await self._send(uow, session, HandoffId(record.handoff_id), message_id, text)

    async def send_agent(
        self, session: Session, handoff_id: HandoffId, message_id: str, text: str
    ) -> HumanMessageReceipt:
        if session.role is not Role.AGENT:
            raise AccessContextError("agent channel requires an agent session")
        async with self._uow_factory(session.access_context()) as uow:
            return await self._send(uow, session, handoff_id, message_id, text)

    async def _send(
        self, uow: UnitOfWork, session: Session, handoff_id: HandoffId, message_id: str, text: str
    ) -> HumanMessageReceipt:
        receipt = await uow.human_service.append(handoff_id, message_id, text, at=self._clock.now())
        if not receipt.replayed:
            await uow.audit.append(
                AuditEvent(
                    event_id=AuditEventId(self._ids.new(IdKind.AUDIT_EVENT)),
                    occurred_at=receipt.message.sent_at,
                    actor_role=session.role,
                    actor_ref=session.customer_id if session.role is Role.CUSTOMER else session.staff_id,
                    action="human_message_sent",
                    target=SourceRef.of(SourceTable.HANDOFFS, handoff_id),
                    outcome=AuditOutcome.SUCCESS,
                    arguments={"message_id": message_id, "conversation_id": receipt.message.conversation_id},
                )
            )
        await uow.commit()
        return receipt
