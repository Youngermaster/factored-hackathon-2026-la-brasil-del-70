from datetime import timedelta

import pytest

from bank_agent.domain.audit import AuditEvent, AuditOutcome
from bank_agent.domain.errors import AccessContextError, AppendOnlyViolationError
from bank_agent.ports.audit import AuditQuery
from bank_agent_builders import T0
from bank_agent_contracts import CONTEXT_A, EVALUATOR, WriteBackend


def _event(event_id: str, minutes: int = 0, action: str = "create_dispute_case") -> AuditEvent:
    return AuditEvent.model_validate(
        {
            "event_id": event_id,
            "occurred_at": T0 + timedelta(minutes=minutes),
            "actor_role": "customer",
            "actor_ref": "CUS-A-0001",
            "action": action,
            "target": "transactions:TXN-A-0001",
            "outcome": AuditOutcome.SUCCESS,
            "arguments": {"reason": "unrecognized", "transaction_id": "[redacted]"},
        }
    )


class TestAuditLogContract:
    async def test_unit_of_work_audit_commits_with_the_transaction(self, write_backend: WriteBackend) -> None:
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.audit.append(_event("aud-000001"))
        async with write_backend.uow_factory()(CONTEXT_A) as uow:
            await uow.audit.append(_event("aud-000002", minutes=1))
            await uow.commit()
        events = await write_backend.audit_log(EVALUATOR).list(AuditQuery())
        assert [event.event_id for event in events] == ["aud-000002"]

    async def test_standalone_log_appends_immediately_and_is_append_only(self, write_backend: WriteBackend) -> None:
        log = write_backend.audit_log(None)
        await log.append(_event("aud-000010", action="login"))
        await log.append(_event("aud-000010", action="login"))
        with pytest.raises(AppendOnlyViolationError):
            await log.append(_event("aud-000010", action="logout"))
        assert len(await write_backend.audit_log(EVALUATOR).list(AuditQuery())) == 1

    async def test_filters_and_orders_events(self, write_backend: WriteBackend) -> None:
        log = write_backend.audit_log(None)
        for index, action in enumerate(("login", "create_dispute_case", "block_card")):
            await log.append(_event(f"aud-00002{index}", minutes=index, action=action))
        reader = write_backend.audit_log(EVALUATOR)
        assert [e.action for e in await reader.list(AuditQuery())] == ["login", "create_dispute_case", "block_card"]
        assert [e.action for e in await reader.list(AuditQuery(action="block_card"))] == ["block_card"]
        window = AuditQuery(since=T0 + timedelta(minutes=1), until=T0 + timedelta(minutes=1))
        assert [e.action for e in await reader.list(window)] == ["create_dispute_case"]
        assert len(await reader.list(AuditQuery(limit=2))) == 2

    async def test_only_evaluators_list(self, write_backend: WriteBackend) -> None:
        for context in (None, CONTEXT_A):
            with pytest.raises(AccessContextError):
                await write_backend.audit_log(context).list(AuditQuery())
