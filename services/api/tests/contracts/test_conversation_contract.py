import pytest

from bank_agent.domain.errors import (
    AccessContextError,
    ConcurrencyConflictError,
    ConversationNotFoundError,
    DuplicateEntityError,
)
from bank_agent.domain.identifiers import ConversationId, TurnId
from bank_agent_builders import conversation, turn
from bank_agent_contracts import AGENT, CONTEXT_A, CONTEXT_B, WriteBackend

CONVERSATION = ConversationId("conv-000001")


async def _seed_conversation(backend: WriteBackend) -> None:
    async with backend.uow_factory()(CONTEXT_A) as uow:
        await uow.conversations.add(conversation())
        await uow.commit()


class TestConversationRepositoryContract:
    async def test_adds_and_reads_back(self, write_backend: WriteBackend) -> None:
        await _seed_conversation(write_backend)
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            assert await uow.conversations.get(CONVERSATION) == conversation()
            with pytest.raises(DuplicateEntityError):
                await uow.conversations.add(conversation())

    async def test_cannot_add_for_another_customer(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_B) as uow:
            with pytest.raises(AccessContextError):
                await uow.conversations.add(conversation())

    async def test_update_uses_optimistic_versions(self, write_backend: WriteBackend) -> None:
        await _seed_conversation(write_backend)
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            current = await uow.conversations.get(CONVERSATION)
            assert current is not None
            stored = await uow.conversations.update(current.evolve(language="es"), expected_version=current.version)
            assert stored.version == current.version + 1
            with pytest.raises(ConcurrencyConflictError):
                await uow.conversations.update(stored, expected_version=current.version)
            with pytest.raises(ConcurrencyConflictError):
                await uow.conversations.update(stored.evolve(customer_id="CUS-B-0002"), expected_version=stored.version)

    async def test_appends_and_lists_turns_in_order(self, write_backend: WriteBackend) -> None:
        await _seed_conversation(write_backend)
        second = turn("9b2f0d1e-0000-4000-8000-000000000002", sequence=2, text="el de 1250")
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.conversations.append_turn(second)
            await uow.conversations.append_turn(turn())
            await uow.commit()
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            turns = await uow.conversations.list_turns(CONVERSATION)
            assert [t.sequence for t in turns] == [1, 2]
            assert await uow.conversations.get_turn(second.turn_id) == second
            assert len(await uow.conversations.list_turns(CONVERSATION, limit=1)) == 1

    async def test_rejects_a_repeated_turn_id_or_sequence(self, write_backend: WriteBackend) -> None:
        await _seed_conversation(write_backend)
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.conversations.append_turn(turn())
            with pytest.raises(DuplicateEntityError):
                await uow.conversations.append_turn(turn())
            with pytest.raises(DuplicateEntityError):
                await uow.conversations.append_turn(turn("9b2f0d1e-0000-4000-8000-000000000003", sequence=1))

    async def test_another_customers_conversation_behaves_like_a_missing_one(self, write_backend: WriteBackend) -> None:
        await _seed_conversation(write_backend)
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.conversations.append_turn(turn())
            await uow.commit()
        async with write_backend.uow_factory()(CONTEXT_B) as uow:
            assert await uow.conversations.get(CONVERSATION) is None
            assert await uow.conversations.get_turn(TurnId(turn().turn_id)) is None
            assert await uow.conversations.list_turns(CONVERSATION) == []
            with pytest.raises(ConversationNotFoundError):
                await uow.conversations.append_turn(turn("9b2f0d1e-0000-4000-8000-000000000004", sequence=2))
            with pytest.raises(ConversationNotFoundError):
                await uow.conversations.update(conversation(), expected_version=0)

    async def test_staff_context_is_refused(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(AGENT) as uow:
            with pytest.raises(AccessContextError):
                await uow.conversations.get(CONVERSATION)
