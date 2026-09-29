"""Chaos: the database goes away mid-turn, before a request, turns read-only, or becomes slow (level L4).

Nothing is ever reported as done: a write cut off by the outage leaves no case, no block, and no turn; the API
answers 503 with ``Retry-After``; the same turn sent again once the database is back runs normally. A slow table
makes the tool time out, retries stay within the budget, and the customer is handed to a person in es and pt.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from bank_agent.domain.actions import ToolName
from bank_agent.domain.errors import DatabaseUnavailableError
from bank_agent.domain.execution_record import ToolCallStatus
from bank_agent.domain.identifiers import ProductId, TurnId
from bank_agent.domain.product import ProductStatus
from bank_agent.domain.workflow import Outcome
from bank_agent_api import ApiBackend, ApiClient
from bank_agent_chaos import DatabaseOutage, OutageBeforeWrite, slow_table
from bank_agent_scenarios import CO, PT
from bank_agent_test_support import PostgresInstance
from bank_agent_workflow_support import Backend
from bank_agent_workflows import build_harness

WEB_LOCALES = Path(__file__).resolve().parents[5] / "apps" / "web" / "src" / "shared" / "i18n" / "locales"
RETRY_TURN = "9b2f0d1e-0000-4000-8000-0000000c4a01"


def test_the_customer_is_told_in_es_and_pt_that_nothing_was_confirmed_and_to_retry() -> None:
    copy = {lang: json.loads((WEB_LOCALES / f"{lang}.json").read_text(encoding="utf-8")) for lang in ("es", "pt")}
    assert "no confirmamos ningún cambio" in copy["es"]["errors"]["unavailable"]
    assert "Inténtalo de nuevo" in copy["es"]["errors"]["unavailable"]
    assert "não confirmamos nenhuma alteração" in copy["pt"]["errors"]["unavailable"]
    assert "Tente de novo" in copy["pt"]["errors"]["unavailable"]


async def test_an_outage_right_before_the_block_write_changes_nothing_and_the_retry_blocks_once(
    postgres_only: Backend, owner: AsyncEngine, migrated_postgres: PostgresInstance
) -> None:
    outage = DatabaseOutage(owner, migrated_postgres.app_user)
    wrapper: list[OutageBeforeWrite] = []

    def cut(tools: object) -> OutageBeforeWrite:
        wrapper.append(OutageBeforeWrite(tools, outage))  # type: ignore[arg-type]
        return wrapper[0]

    harness = build_harness(postgres_only.uow_factory, postgres_only.session_store, wrap_tools=cut)
    session = harness.session(CO, step_up=True)
    try:
        first = await harness.say("Perdí mi tarjeta, bloquéala por favor", session)
        assert first.state == "CONFIRM_BLOCK"
        with pytest.raises(DatabaseUnavailableError):
            await harness.say("sí", session, first.conversation_id, turn=RETRY_TURN)
        assert wrapper[0].triggered
    finally:
        await outage.end()
    async with harness.uow_factory(session.access_context()) as uow:
        card = await uow.products.get(ProductId("PRD-FIXCO-CRED"))
        assert await uow.conversations.get_turn(TurnId(RETRY_TURN)) is None
    assert card is not None
    assert card.status is not ProductStatus.BLOCKED

    done = await harness.say("sí", session, first.conversation_id, turn=RETRY_TURN)
    assert (done.state, done.outcome) == ("RESOLVED", Outcome.RESOLVED)
    assert "bloqueamos tu tarjeta de crédito **** 9999" in done.response.text
    record = await harness.record(session, RETRY_TURN)
    (block,) = [call for call in record.tool_calls if call.tool is ToolName.BLOCK_CARD]
    assert block.verification is not None
    assert block.verification.verified


async def test_the_api_answers_503_with_retry_after_and_the_same_turn_succeeds_after(
    postgres_api: ApiBackend, owner: AsyncEngine, migrated_postgres: PostgresInstance
) -> None:
    harness = postgres_api.build()
    outage = DatabaseOutage(owner, migrated_postgres.app_user)
    async with ApiClient(harness.app) as client:
        await client.login("persona-co")
        conversation = await client.open_conversation()
        async with outage.during():
            refused = await client.say(conversation, "¿Cuál es mi saldo?", turn_id=RETRY_TURN)
            ready = await client.get("/health/ready")
            details = await client.get("/health/details")
        assert refused.status_code == 503
        assert refused.headers["Retry-After"] == "30"
        problem = refused.json()
        assert problem["type"].endswith("/dependency-unavailable")
        assert "bank_app" not in refused.text
        assert "53300" not in refused.text
        assert (ready.status_code, ready.json()["checks"]) == (503, {"database": "unavailable"})
        assert (details.status_code, details.json()["level"]) == (503, "L4")
        assert details.json()["reasons"] == ["database_unavailable"]

        again = await client.say(conversation, "¿Cuál es mi saldo?", turn_id=RETRY_TURN)
        assert again.status_code == 200, again.text
        assert again.json()["replayed"] is False
        assert (await client.get("/health/details")).json()["level"] == "L0"


async def test_a_read_only_database_is_not_ready_and_refuses_signed_in_requests(
    postgres_api: ApiBackend, owner: AsyncEngine, migrated_postgres: PostgresInstance
) -> None:
    """Even a history read refreshes the session's last-seen time, so a read-only server fails closed for it too."""
    harness = postgres_api.build()
    outage = DatabaseOutage(owner, migrated_postgres.app_user)
    async with ApiClient(harness.app) as client:
        await client.login("persona-co")
        conversation = await client.open_conversation()
        async with outage.during(read_only=True):
            history = await client.get(f"/v1/conversations/{conversation}")
            refused = await client.say(conversation, "¿Cuál es mi saldo?")
            ready = await client.get("/health/ready")
            level = (await client.get("/health/details")).json()["level"]
        for response in (history, refused):
            assert (response.status_code, response.headers["Retry-After"]) == (503, "30")
            assert response.json()["type"].endswith("/dependency-unavailable")
        assert (ready.status_code, level) == (503, "L4")
        assert (await client.get(f"/v1/conversations/{conversation}")).status_code == 200


@pytest.mark.parametrize(
    ("customer", "text", "handed_off"),
    [(CO, "Perdí mi tarjeta, bloquéala por favor", "persona del equipo"),
     (PT, "Quero bloquear meu cartão", "pessoa da equipe")],
)  # fmt: skip
async def test_a_slow_database_times_the_tool_out_within_the_retry_budget_and_hands_off(
    postgres_only: Backend, owner: AsyncEngine, customer: str, text: str, handed_off: str
) -> None:
    harness = build_harness(postgres_only.uow_factory, postgres_only.session_store, tool_timeout_seconds=0.3)
    session = harness.session(customer, step_up=True)
    async with slow_table(owner, "products"):
        reply = await harness.say(text, session)
    assert (reply.state, reply.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert handed_off in reply.response.text
    assert "bloqueamos" not in reply.response.text
    record = await harness.record(session, reply.turn_id)
    failed = [call for call in record.tool_calls if call.status is ToolCallStatus.FAILED]
    assert [(call.error_code, call.attempts) for call in failed] == [("tool_timeout", 3)]
    assert record.handoff_ref is not None
    handoff = await harness.handoff(session, record.handoff_ref)
    assert handoff.handoff.escalation_reason.code.value == "tool_failure"
