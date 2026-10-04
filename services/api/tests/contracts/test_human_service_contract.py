"""Shared human exchange contracts over memory and PostgreSQL, using team-made synthetic fixtures."""

from datetime import timedelta

import pytest

from bank_agent.domain.access import AccessContext, Role
from bank_agent.domain.errors import (
    AccessContextError,
    HandoffNotFoundError,
    IdempotencyConflictError,
    InvalidHandoffTransitionError,
)
from bank_agent.domain.handoff import HandoffOutcomeCode
from bank_agent.domain.identifiers import ConversationId, HandoffId, StaffId
from bank_agent_builders import T0, conversation, handoff
from bank_agent_contracts import AGENT, CONTEXT_A, CONTEXT_B, EVALUATOR, WriteBackend

HANDOFF = HandoffId("ho-000001")
CONVERSATION = ConversationId("conv-000001")
OTHER_AGENT = AccessContext.for_staff(Role.AGENT, StaffId("agent-other"))


async def seed(backend: WriteBackend) -> None:
    async with backend.uow_factory()(CONTEXT_A) as uow:
        await uow.conversations.add(conversation())
        await uow.handoffs.add(handoff())
        await uow.commit()


class TestHumanServiceRepositoryContract:
    async def test_customer_can_send_while_queued_and_agent_joins_the_same_conversation(
        self, write_backend: WriteBackend
    ) -> None:
        await seed(write_backend)
        factory = write_backend.uow_factory()
        async with factory(CONTEXT_A) as uow:
            record = await uow.human_service.for_conversation(CONVERSATION)
            assert record is not None
            assert record.handoff_id == HANDOFF
            receipt = await uow.human_service.append(HANDOFF, "msg-customer", "Preciso de ajuda", at=T0)
            assert receipt.message.role == "user"
            assert not receipt.replayed
            await uow.commit()
        async with factory(AGENT) as uow:
            with pytest.raises(HandoffNotFoundError):
                await uow.human_service.messages(HANDOFF)
            await uow.handoffs.claim(HANDOFF, at=T0)
            reply = await uow.human_service.append(HANDOFF, "msg-agent", "Posso ajudar", at=T0)
            assert reply.message.role == "agent"
            assert reply.message.conversation_id == CONVERSATION
            await uow.commit()
        async with factory(CONTEXT_A) as uow:
            messages = await uow.human_service.messages(HANDOFF)
            assert [m.text for m in messages] == ["Preciso de ajuda", "Posso ajudar"]
            assert [m.sequence for m in messages] == [1, 2]
            page = await uow.human_service.messages(HANDOFF, after=1, limit=1)
            assert [m.message_id for m in page] == ["msg-agent"]

    async def test_replay_and_changed_message_id_are_distinct(self, write_backend: WriteBackend) -> None:
        await seed(write_backend)
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            first = await uow.human_service.append(HANDOFF, "msg-1", "Ayuda", at=T0)
            replay = await uow.human_service.append(HANDOFF, "msg-1", "Ayuda", at=T0 + timedelta(seconds=1))
            assert replay.message == first.message
            assert replay.replayed
            with pytest.raises(IdempotencyConflictError):
                await uow.human_service.append(HANDOFF, "msg-1", "Otro texto", at=T0)
            assert len(await uow.human_service.messages(HANDOFF)) == 1

    async def test_customer_and_staff_isolation_even_for_an_empty_page(self, write_backend: WriteBackend) -> None:
        await seed(write_backend)
        for context in (CONTEXT_B, AGENT, OTHER_AGENT):
            async with write_backend.uow_factory()(context) as uow:
                with pytest.raises(HandoffNotFoundError):
                    await uow.human_service.messages(HANDOFF, after=999)
                with pytest.raises(HandoffNotFoundError):
                    await uow.human_service.append(HANDOFF, "msg-foreign", "Ayuda", at=T0)
        async with write_backend.uow_factory()(EVALUATOR) as uow:
            with pytest.raises(AccessContextError):
                await uow.human_service.messages(HANDOFF)
        async with write_backend.uow_factory()(CONTEXT_B) as uow:
            assert await uow.human_service.for_conversation(CONVERSATION) is None

    async def test_another_agent_cannot_read_or_reply_to_a_claimed_handoff(self, write_backend: WriteBackend) -> None:
        await seed(write_backend)
        async with write_backend.uow_factory()(AGENT) as uow:
            await uow.handoffs.claim(HANDOFF, at=T0)
            await uow.commit()
        async with write_backend.uow_factory()(OTHER_AGENT) as uow:
            with pytest.raises(HandoffNotFoundError):
                await uow.human_service.messages(HANDOFF)
            with pytest.raises(HandoffNotFoundError):
                await uow.human_service.append(HANDOFF, "msg-agent-other", "Ayuda", at=T0)
            with pytest.raises(AccessContextError):
                await uow.human_service.for_conversation(CONVERSATION)

    async def test_closed_thread_stays_readable_and_retries_replay_but_new_sends_fail(
        self, write_backend: WriteBackend
    ) -> None:
        await seed(write_backend)
        factory = write_backend.uow_factory()
        async with factory(CONTEXT_A) as uow:
            await uow.human_service.append(HANDOFF, "msg-original", "Ayuda", at=T0)
            await uow.commit()
        async with factory(AGENT) as uow:
            await uow.handoffs.claim(HANDOFF, at=T0)
            await uow.handoffs.resolve(HANDOFF, outcome=HandoffOutcomeCode.RESOLVED_BY_AGENT, note="Resolved", at=T0)
            await uow.commit()
        for context in (CONTEXT_A, AGENT):
            async with factory(context) as uow:
                assert len(await uow.human_service.messages(HANDOFF)) == 1
                with pytest.raises(InvalidHandoffTransitionError):
                    await uow.human_service.append(HANDOFF, "msg-new", "Ayuda", at=T0)
        async with factory(CONTEXT_A) as uow:
            assert (await uow.human_service.append(HANDOFF, "msg-original", "Ayuda", at=T0)).replayed

    async def test_rollback_discards_messages(self, write_backend: WriteBackend) -> None:
        await seed(write_backend)
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.human_service.append(HANDOFF, "msg-rollback", "Ayuda", at=T0)
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            assert await uow.human_service.messages(HANDOFF) == []

    async def test_send_and_resolve_cannot_both_commit_from_the_same_lifecycle_snapshot(
        self, write_backend: WriteBackend
    ) -> None:
        from bank_agent.domain.errors import ConcurrencyConflictError

        await seed(write_backend)
        factory = write_backend.uow_factory()
        async with factory(AGENT) as uow:
            await uow.handoffs.claim(HANDOFF, at=T0)
            await uow.commit()
        async with factory(CONTEXT_A) as sending, factory(AGENT) as closing:
            await sending.human_service.append(HANDOFF, "msg-race", "Ayuda", at=T0)
            try:
                await closing.handoffs.resolve(
                    HANDOFF, outcome=HandoffOutcomeCode.RESOLVED_BY_AGENT, note="Resolved", at=T0
                )
            except ConcurrencyConflictError:
                await sending.commit()
            else:
                await sending.commit()
                with pytest.raises(ConcurrencyConflictError):
                    await closing.commit()
        async with factory(AGENT) as uow:
            await uow.handoffs.resolve(HANDOFF, outcome=HandoffOutcomeCode.RESOLVED_BY_AGENT, note="Resolved", at=T0)
            await uow.commit()
        async with factory(CONTEXT_A) as uow:
            assert len(await uow.human_service.messages(HANDOFF)) == 1
            with pytest.raises(InvalidHandoffTransitionError):
                await uow.human_service.append(HANDOFF, "msg-after-close", "Ayuda", at=T0)
