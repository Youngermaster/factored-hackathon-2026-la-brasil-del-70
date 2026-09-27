"""Audit events for tool calls, with redacted arguments.

Only argument keys on an allowlist keep their value (enumerations, codes, counts); every other value, such as
identifiers, amounts, and declared income, is replaced by ``[redacted]``. The event's target already names the
record the call acted on.
"""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import JsonValue

from bank_agent.application.tools.context import SessionContext
from bank_agent.domain.actions import ToolName
from bank_agent.domain.audit import AuditEvent, AuditOutcome
from bank_agent.domain.identifiers import AuditEventId, IdKind, SourceRef
from bank_agent.ports.audit import AuditLog
from bank_agent.ports.determinism import IdGenerator

REDACTED = "[redacted]"
VISIBLE_ARGUMENTS = frozenset(
    {"reason", "statuses", "types", "limit", "product_code", "requested_term_months", "purpose", "period_days"}
)


def _plain(value: object) -> JsonValue:
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, bool | int | str) or value is None:
        return value
    if isinstance(value, Decimal | date | datetime):
        return str(value)
    if isinstance(value, list | tuple | set | frozenset):
        items: list[JsonValue] = []
        items.extend(sorted(str(_plain(item)) for item in value))
        return items
    return REDACTED


def redact_arguments(arguments: Mapping[str, object]) -> dict[str, JsonValue]:
    return {name: _plain(value) if name in VISIBLE_ARGUMENTS else REDACTED for name, value in arguments.items()}


async def record_call(
    audit: AuditLog,
    ids: IdGenerator,
    context: SessionContext,
    tool: ToolName,
    outcome: AuditOutcome,
    *,
    target: SourceRef | None = None,
    arguments: Mapping[str, object] | None = None,
) -> None:
    await audit.append(
        AuditEvent(
            event_id=AuditEventId(ids.new(IdKind.AUDIT_EVENT)),
            occurred_at=context.at,
            actor_role=context.session.role,
            actor_ref=context.actor_ref,
            action=tool.value,
            target=target,
            outcome=outcome,
            arguments=redact_arguments(arguments or {}),
        )
    )
