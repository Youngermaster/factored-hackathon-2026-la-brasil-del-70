"""A write that paused for a step-up reads the next message before it runs (production QA finding R2).

"no, mejor no la bloquees" sent after the step-up used to block the card anyway, because the working state ran the
write without reading the message. Now a refusal cancels with the "nothing was recorded" reply, an unrelated
message asks the confirmation again, and only the step-up continuation or a yes runs the write. The same holds for
the dispute case and the credit application intake."""

import pytest

from bank_agent.domain.actions import ToolName
from bank_agent.domain.product import ProductStatus
from bank_agent.domain.session import Session
from bank_agent.domain.workflow import Outcome
from bank_agent_scenarios import CO, MX, PT
from bank_agent_workflow_support import Backend, cases
from bank_agent_workflows import Harness, build_harness

BLOCK_REQUEST = {CO: "Perdí mi tarjeta, bloquéala por favor", PT: "Roubaram meu cartão de crédito, quero bloquear"}
YES = {CO: "sí", PT: "sim"}
CARD = {CO: "PRD-FIXCO-CRED", PT: "PRD-FIXPT-CRED"}
NOTHING = {CO: "no registré nada", PT: "não registrei nada"}
DISPUTE_OPENING = "No reconozco un cargo de 1250 pesos en FIXTURE MARKET del 15 de junio"
CREDIT_OPENING = "Sou elegível para um cartão de crédito com limite de 30 mil pesos?"


def _stepped_up(harness: Harness, customer: str) -> Session:
    return harness.session(customer, step_up=True, session_id=f"ses-{customer.lower()}-stepped")


async def _paused_block(harness: Harness, customer: str) -> str:
    first = await harness.say(BLOCK_REQUEST[customer], harness.session(customer))
    assert first.state == "CONFIRM_BLOCK"
    pending = await harness.say(YES[customer], harness.session(customer), first.conversation_id)
    assert (pending.state, pending.response.step_up_required) == ("EXECUTE", True)
    return first.conversation_id


async def _card_status(harness: Harness, session: Session, product_id: str) -> ProductStatus:
    async with harness.uow_factory(session.access_context()) as uow:
        card = await uow.products.get(product_id)  # type: ignore[arg-type]
    assert card is not None
    return card.status


@pytest.mark.parametrize(
    ("customer", "text"),
    [
        (CO, "no, mejor no la bloquees"),
        (CO, "cancela el bloqueo"),
        (PT, "não, não bloqueie"),
        (PT, "desisto"),
    ],
)
async def test_a_refusal_after_the_step_up_cancels_the_block_and_nothing_is_recorded(
    backend: Backend, customer: str, text: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    conversation_id = await _paused_block(harness, customer)
    stepped = _stepped_up(harness, customer)
    reply = await harness.say(text, stepped, conversation_id)
    assert (reply.state, reply.outcome) == ("RESOLVED", Outcome.RESOLVED)
    assert reply.response.template_id == "common.nothing_recorded"
    assert NOTHING[customer] in reply.response.text
    assert reply.response.action_statuses == ()
    record = await harness.record(stepped, reply.turn_id)
    assert all(call.tool is not ToolName.BLOCK_CARD for call in record.tool_calls)
    assert await _card_status(harness, stepped, CARD[customer]) is ProductStatus.ACTIVE


@pytest.mark.parametrize(
    ("customer", "text"),
    [
        (CO, "¿cuál es el horario de las sucursales?"),
        (CO, "listo, pero mejor no"),
        (PT, "qual é o horário das agências?"),
        (PT, "pronto, mas melhor não"),
    ],
)
async def test_an_unrelated_or_mixed_message_after_the_step_up_never_runs_the_block(
    memory_only: Backend, customer: str, text: str
) -> None:
    harness = build_harness(memory_only.uow_factory, memory_only.session_store)
    conversation_id = await _paused_block(harness, customer)
    stepped = _stepped_up(harness, customer)
    reply = await harness.say(text, stepped, conversation_id)
    assert reply.state == "CONFIRM_BLOCK"
    assert reply.response.action_statuses == ()
    assert await _card_status(harness, stepped, CARD[customer]) is ProductStatus.ACTIVE
    record = await harness.record(stepped, reply.turn_id)
    assert all(call.tool is not ToolName.BLOCK_CARD for call in record.tool_calls)


@pytest.mark.parametrize(
    ("customer", "text"),
    [(CO, "Listo, ya confirmé mi identidad"), (CO, "sí"), (PT, "Pronto, já confirmei minha identidade"), (PT, "sim")],
)
async def test_the_step_up_continuation_still_blocks_the_card_and_verifies_it(
    backend: Backend, customer: str, text: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    conversation_id = await _paused_block(harness, customer)
    stepped = _stepped_up(harness, customer)
    done = await harness.say(text, stepped, conversation_id)
    assert (done.state, done.outcome) == ("RESOLVED", Outcome.RESOLVED)
    assert done.response.template_id != "common.nothing_recorded"
    assert await _card_status(harness, stepped, CARD[customer]) is ProductStatus.BLOCKED


async def test_a_refusal_after_the_step_up_opens_no_dispute_case(memory_only: Backend) -> None:
    harness = build_harness(memory_only.uow_factory, memory_only.session_store)
    session = harness.session(MX)
    first = await harness.say(DISPUTE_OPENING, session)
    await harness.say("no", session, first.conversation_id)
    pending = await harness.say("sí", session, first.conversation_id)
    assert (pending.state, pending.response.step_up_required) == ("EXECUTE", True)
    stepped = _stepped_up(harness, MX)
    reply = await harness.say("no, mejor no abras el caso", stepped, first.conversation_id)
    assert reply.response.template_id == "common.nothing_recorded"
    assert await cases(harness, stepped) == []


async def test_a_refusal_after_the_step_up_records_no_credit_intake(memory_only: Backend) -> None:
    harness = build_harness(memory_only.uow_factory, memory_only.session_store)
    session = harness.session(PT)
    first = await harness.say(CREDIT_OPENING, session)
    await harness.say("sim", session, first.conversation_id)
    pending = await harness.say("sim", session, first.conversation_id)
    assert (pending.state, pending.response.step_up_required) == ("EXECUTE", True)
    stepped = _stepped_up(harness, PT)
    reply = await harness.say("não, desisto", stepped, first.conversation_id)
    assert reply.response.template_id == "common.nothing_recorded"
    async with harness.uow_factory(stepped.access_context()) as uow:
        assert await uow.credit_applications.list_mine() == []
