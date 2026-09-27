from datetime import timedelta

import pytest

from bank_agent.domain.errors import AccessContextError, AppendOnlyViolationError
from bank_agent.domain.execution_record import ExecutionRecord
from bank_agent.domain.identifiers import ConversationId, TurnId
from bank_agent_builders import T0, execution_record
from bank_agent_contracts import AGENT, CONTEXT_A, CONTEXT_B, EVALUATOR, WriteBackend

TURN_1 = "9b2f0d1e-0000-4000-8000-000000000001"
TURN_2 = "9b2f0d1e-0000-4000-8000-000000000002"


class TestExecutionRecordRepositoryContract:
    async def test_appends_and_lists_in_time_order(self, write_backend: WriteBackend) -> None:
        later = execution_record(TURN_2, recorded_at=T0 + timedelta(seconds=5))
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.execution_records.append(later)
            await uow.execution_records.append(execution_record(TURN_1))
            await uow.commit()
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            records = await uow.execution_records.list_for_conversation(ConversationId("conv-000001"))
            assert [r.turn_id for r in records] == [TURN_1, TURN_2]
            assert await uow.execution_records.get(TurnId(TURN_2)) == later

    async def test_is_append_only(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.execution_records.append(execution_record(TURN_1))
            await uow.execution_records.append(execution_record(TURN_1))
            with pytest.raises(AppendOnlyViolationError):
                await uow.execution_records.append(execution_record(TURN_1, state_after="CLARIFY"))
        assert not hasattr(ExecutionRecord, "reasoning")
        repository_methods = {name for name in dir(type(uow.execution_records)) if not name.startswith("_")}
        assert repository_methods == {"append", "get", "list_for_conversation"}

    async def test_customers_see_only_their_own_records(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.execution_records.append(execution_record(TURN_1))
            await uow.commit()
        async with write_backend.uow_factory()(CONTEXT_B) as uow:
            assert await uow.execution_records.get(TurnId(TURN_1)) is None
            assert await uow.execution_records.list_for_conversation(ConversationId("conv-000001")) == []
            with pytest.raises(AccessContextError):
                await uow.execution_records.append(execution_record(TURN_2))

    async def test_evaluators_read_every_record_but_never_append(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.execution_records.append(execution_record(TURN_1))
            await uow.commit()
        async with write_backend.uow_factory()(EVALUATOR) as uow:
            assert await uow.execution_records.get(TurnId(TURN_1)) is not None
            with pytest.raises(AccessContextError):
                await uow.execution_records.append(execution_record(TURN_2))

    async def test_agents_are_refused(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(AGENT) as uow:
            with pytest.raises(AccessContextError):
                await uow.execution_records.get(TurnId(TURN_1))
