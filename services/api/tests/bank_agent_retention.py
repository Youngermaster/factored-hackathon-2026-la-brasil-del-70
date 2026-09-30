"""Retention fixtures: real conversations, sessions, and credit intakes at chosen instants, then row counts.

The rows come from the API and the repositories (never hand-written SQL), so the purge is tested against documents the
service really stores. Shared by the purge suite and the non-superuser owner suite.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from bank_agent.domain.access import AccessContext
from bank_agent.domain.credit import ApplicationStatus, CreditApplicationIntake
from bank_agent.domain.identifiers import ApplicationId, CreditProductCode, CustomerId, IdempotencyKey
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.retention import RetentionPolicy
from bank_agent.ports.unit_of_work import UnitOfWorkFactory
from bank_agent_api import ApiClient, ApiHarness
from bank_agent_scenarios import MX

POLICY = RetentionPolicy(conversation_days=7, session_days=7, credit_application_days=30)
COUNTED_TABLES = (
    "messages",
    "turns",
    "conversations",
    "sessions",
    "otp_challenges",
    "trust_events",
    "credit_applications",
    "execution_records",
    "audit_events",
)


@dataclass(frozen=True)
class Populated:
    old_conversation: str
    recent_conversation: str


async def chat_at(harness: ApiHarness, at: datetime, persona: str, text_: str = "¿Cuál es mi saldo?") -> str:
    """Log in and send one turn with the clock at ``at``; returns the conversation id."""
    harness.clock.set(at)
    async with ApiClient(harness.app) as client:
        await client.login(persona)
        conversation = await client.open_conversation()
        sent = await client.say(conversation, text_)
        assert sent.status_code == 200, sent.text
        await client.post("/v1/auth/logout")
    return conversation


async def intake_at(
    factory: UnitOfWorkFactory, number: int, created: datetime, *, withdrawn_at: datetime | None = None
) -> ApplicationId:
    """A submitted credit intake for the fixture customer, optionally withdrawn at ``withdrawn_at``."""
    context = AccessContext.for_customer(CustomerId(MX))
    intake = CreditApplicationIntake.submit(
        application_id=ApplicationId(f"app-ret-{number:04d}"),
        customer_id=CustomerId(MX),
        product_code=CreditProductCode("MX-PL-STANDARD"),
        requested_amount=Money.of("30000.00", Currency.MXN),
        requested_term_months=12,
        purpose="general_purpose",
        idempotency_key=IdempotencyKey(f"idem-key-retention-{number:06d}"),
        created_at=created,
    )
    async with factory(context) as uow:
        stored = await uow.credit_applications.create(intake)
        if withdrawn_at is not None:
            await uow.credit_applications.transition(
                stored.application_id,
                ApplicationStatus.WITHDRAWN,
                expected_version=stored.version,
                at=withdrawn_at,
                reason_code="customer_withdrew",
            )
        await uow.commit()
    return stored.application_id


async def row_counts(engine: AsyncEngine, superuser: bool = True) -> dict[str, int]:
    """Rows per counted table, read by a role that sees every row (a superuser, or the owner in its context)."""
    async with engine.begin() as connection:
        if not superuser:
            await connection.execute(text("SELECT set_config('app.role', 'retention', true)"))
        counts = {}
        for table in COUNTED_TABLES:
            if not superuser and table in ("execution_records", "audit_events"):
                continue
            result = await connection.execute(text(f"SELECT count(*) FROM app.{table}"))  # noqa: S608  # nosec B608
            counts[table] = int(result.scalar_one())
        return counts


def days(count: float) -> timedelta:
    return timedelta(days=count)
