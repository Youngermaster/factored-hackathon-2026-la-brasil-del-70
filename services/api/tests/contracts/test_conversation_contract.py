from datetime import timedelta

import pytest

from bank_agent.domain.conversation import ConversationCreationQuota
from bank_agent.domain.errors import (
    AccessContextError,
    ConcurrencyConflictError,
    ConversationCreationLimitedError,
    ConversationNotFoundError,
    DuplicateEntityError,
)
from bank_agent.domain.identifiers import ConversationId, TurnId
from bank_agent_builders import T0, conversation, turn
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


class TestConversationCreationQuotaContract:
    async def test_five_chats_are_allowed_across_sessions_and_the_sixth_waits_one_hour(
        self, write_backend: WriteBackend
    ) -> None:
        factory = write_backend.uow_factory()
        for index in range(5):
            async with factory(CONTEXT_A) as uow:
                await uow.conversations.add_with_quota(conversation(f"conv-limit-{index}", created_at=T0))
                await uow.commit()
        async with factory(CONTEXT_A) as uow:
            with pytest.raises(ConversationCreationLimitedError) as refused:
                await uow.conversations.add_with_quota(conversation("conv-limit-refused", created_at=T0))
            assert refused.value.retry_after == timedelta(hours=1)
        async with factory(CONTEXT_B) as uow:
            await uow.conversations.add_with_quota(
                conversation("conv-limit-b", customer_id="CUS-B-0002", created_at=T0)
            )
            await uow.commit()
        async with factory(CONTEXT_A) as uow:
            await uow.conversations.add_with_quota(
                conversation("conv-limit-boundary", created_at=T0 + timedelta(hours=1))
            )
            await uow.commit()

    async def test_a_configured_limit_and_window_replace_the_defaults(self, write_backend: WriteBackend) -> None:
        factory = write_backend.uow_factory_with_quota(ConversationCreationQuota(limit=2, window=timedelta(minutes=10)))
        for index, minutes in enumerate((0, 3)):
            async with factory(CONTEXT_A) as uow:
                created_at = T0 + timedelta(minutes=minutes)
                await uow.conversations.add_with_quota(conversation(f"conv-config-{index}", created_at=created_at))
                await uow.commit()
        async with factory(CONTEXT_A) as uow:
            with pytest.raises(ConversationCreationLimitedError) as refused:
                await uow.conversations.add_with_quota(
                    conversation("conv-config-refused", created_at=T0 + timedelta(minutes=4))
                )
            assert refused.value.retry_after == timedelta(minutes=6)
        async with factory(CONTEXT_A) as uow:
            # At exactly ten minutes the first creation leaves the configured window.
            await uow.conversations.add_with_quota(
                conversation("conv-config-boundary", created_at=T0 + timedelta(minutes=10))
            )
            await uow.commit()

    async def test_a_higher_configured_limit_admits_more_than_five_chats(self, write_backend: WriteBackend) -> None:
        factory = write_backend.uow_factory_with_quota(ConversationCreationQuota(limit=8))
        for index in range(8):
            async with factory(CONTEXT_A) as uow:
                await uow.conversations.add_with_quota(conversation(f"conv-high-{index}", created_at=T0))
                await uow.commit()
        async with factory(CONTEXT_A) as uow:
            with pytest.raises(ConversationCreationLimitedError) as refused:
                await uow.conversations.add_with_quota(conversation("conv-high-refused", created_at=T0))
            assert refused.value.retry_after == timedelta(hours=1)

    async def test_a_lowered_limit_waits_for_the_creation_that_frees_a_slot(self, write_backend: WriteBackend) -> None:
        for minutes in range(3):
            async with write_backend.uow_factory()(CONTEXT_A) as uow:
                created_at = T0 + timedelta(minutes=minutes)
                await uow.conversations.add_with_quota(conversation(f"conv-lowered-{minutes}", created_at=created_at))
                await uow.commit()
        lowered = write_backend.uow_factory_with_quota(ConversationCreationQuota(limit=2))
        async with lowered(CONTEXT_A) as uow:
            with pytest.raises(ConversationCreationLimitedError) as refused:
                await uow.conversations.add_with_quota(
                    conversation("conv-lowered-refused", created_at=T0 + timedelta(minutes=3))
                )
            # Two of the three creations must leave the window; the second leaves at T0 + 61 minutes.
            assert refused.value.retry_after == timedelta(minutes=58)

    async def test_failed_creates_do_not_count(self, write_backend: WriteBackend) -> None:
        for index in range(7):
            async with write_backend.uow_factory()(CONTEXT_A) as uow:
                await uow.conversations.add_with_quota(conversation(f"conv-rollback-{index}"))
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.conversations.add_with_quota(conversation("conv-limit-real"))
            await uow.commit()

    async def test_competing_creations_cannot_both_commit_the_last_available_slot(
        self, write_backend: WriteBackend
    ) -> None:
        factory = write_backend.uow_factory()
        for index in range(4):
            async with factory(CONTEXT_A) as uow:
                await uow.conversations.add_with_quota(conversation(f"conv-race-{index}"))
                await uow.commit()
        async with factory(CONTEXT_A) as first, factory(CONTEXT_A) as second:
            await first.conversations.add_with_quota(conversation("conv-race-first"))
            try:
                await second.conversations.add_with_quota(conversation("conv-race-second"))
            except ConcurrencyConflictError:
                pass  # PostgreSQL refuses the concurrent attempt before insertion.
            else:
                await first.commit()
                with pytest.raises(ConcurrencyConflictError):
                    await second.commit()
                return
            await first.commit()
