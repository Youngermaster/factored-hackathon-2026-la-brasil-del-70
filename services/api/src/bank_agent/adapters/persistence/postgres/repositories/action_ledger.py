"""The action ledger over ``app.action_idempotency``."""

from bank_agent.adapters.persistence.postgres.repositories.access import customer_of
from bank_agent.adapters.persistence.postgres.transaction import Row, Tx
from bank_agent.domain.actions import ActionKind, ActionLedgerEntry
from bank_agent.domain.errors import IdempotencyConflictError
from bank_agent.domain.identifiers import IdempotencyKey, SourceRef


def _entry(row: Row) -> ActionLedgerEntry:
    return ActionLedgerEntry(
        action=ActionKind(row["action"]),
        idempotency_key=row["idempotency_key"],
        target=SourceRef.model_validate(row["target"]),
        request_digest=row["request_digest"],
        outcome=row["outcome"],
        recorded_at=row["recorded_at"],
    )


class PostgresActionLedger:
    def __init__(self, tx: Tx) -> None:
        self._tx = tx

    async def find(self, action: ActionKind, key: IdempotencyKey) -> ActionLedgerEntry | None:
        row = await self._tx.one_or_none(
            "SELECT * FROM app.action_idempotency WHERE customer_id = :customer AND action = :action "
            "AND idempotency_key = :key",
            {"customer": customer_of(self._tx.context), "action": action.value, "key": key},
        )
        return _entry(row) if row is not None else None

    async def record(self, entry: ActionLedgerEntry) -> ActionLedgerEntry:
        inserted = await self._tx.execute(
            "INSERT INTO app.action_idempotency (customer_id, action, idempotency_key, target, request_digest, "
            "outcome, recorded_at) VALUES (:customer, :action, :key, :target, :digest, :outcome, :recorded_at) "
            "ON CONFLICT (customer_id, action, idempotency_key) DO NOTHING",
            {
                "customer": customer_of(self._tx.context),
                "action": entry.action.value,
                "key": entry.idempotency_key,
                "target": str(entry.target),
                "digest": entry.request_digest,
                "outcome": entry.outcome,
                "recorded_at": entry.recorded_at,
            },
        )
        if inserted == 1:
            return entry
        existing = await self.find(entry.action, entry.idempotency_key)
        if existing is None or existing.request_digest != entry.request_digest:
            raise IdempotencyConflictError()
        return existing
