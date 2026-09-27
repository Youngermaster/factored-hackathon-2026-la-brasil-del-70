import pytest

from bank_agent.domain.actions import ActionKind, ActionLedgerEntry
from bank_agent.domain.errors import AccessContextError, IdempotencyConflictError
from bank_agent.domain.identifiers import IdempotencyKey
from bank_agent_builders import T0
from bank_agent_contracts import AGENT, CONTEXT_A, CONTEXT_B, WriteBackend

KEY = IdempotencyKey("idem-key-fixture-block-0001")


def _entry(digest: str = "a" * 64, target: str = "products:PRD-A-CARD") -> ActionLedgerEntry:
    return ActionLedgerEntry.model_validate(
        {
            "action": ActionKind.BLOCK_CARD,
            "idempotency_key": KEY,
            "target": target,
            "request_digest": digest,
            "outcome": "blocked",
            "recorded_at": T0,
        }
    )


class TestActionLedgerContract:
    async def test_records_once_and_replays_the_first_outcome(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            assert await uow.action_ledger.find(ActionKind.BLOCK_CARD, KEY) is None
            assert await uow.action_ledger.record(_entry()) == _entry()
            await uow.commit()
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            assert await uow.action_ledger.record(_entry()) == _entry()
            assert await uow.action_ledger.find(ActionKind.BLOCK_CARD, KEY) == _entry()
            with pytest.raises(IdempotencyConflictError):
                await uow.action_ledger.record(_entry(digest="b" * 64))

    async def test_keys_are_per_customer(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.action_ledger.record(_entry())
            await uow.commit()
        async with write_backend.uow_factory()(CONTEXT_B) as uow:
            assert await uow.action_ledger.find(ActionKind.BLOCK_CARD, KEY) is None
            other = _entry(digest="c" * 64, target="products:PRD-B-CARD")
            assert await uow.action_ledger.record(other) == other

    async def test_uncommitted_entries_are_discarded(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.action_ledger.record(_entry())
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            assert await uow.action_ledger.find(ActionKind.BLOCK_CARD, KEY) is None

    async def test_staff_contexts_are_refused(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(AGENT) as uow:
            with pytest.raises(AccessContextError):
                await uow.action_ledger.find(ActionKind.BLOCK_CARD, KEY)
