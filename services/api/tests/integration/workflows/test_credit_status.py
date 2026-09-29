"""Credit application status without an application id: ``list_my_credit_applications`` answers one intake, lists
several (newest three), or says there is none and offers the catalog, on the in-memory adapters and PostgreSQL."""

from datetime import UTC, datetime, timedelta

from bank_agent.domain.credit import CreditApplicationIntake
from bank_agent.domain.identifiers import ApplicationId, CreditProductCode, CustomerId, IdempotencyKey
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.workflow import Outcome
from bank_agent.policy.lexicon import approval_terms
from bank_agent_scenarios import CO, MX, PT
from bank_agent_workflow_support import Backend
from bank_agent_workflows import Harness, build_harness

SENT = datetime(2026, 6, 1, 15, 0, tzinfo=UTC)


async def _seed(harness: Harness, customer: str, *codes: str) -> list[str]:
    """Store one submitted intake per product code, a day apart, oldest first; returns their ids."""
    ids: list[str] = []
    async with harness.uow_factory(harness.session(customer).access_context()) as uow:
        for index, code in enumerate(codes):
            application_id = f"app-{customer[-4:].lower()}{index:02d}"
            await uow.credit_applications.create(
                CreditApplicationIntake.submit(
                    application_id=ApplicationId(application_id),
                    customer_id=CustomerId(customer),
                    product_code=CreditProductCode(code),
                    requested_amount=Money.of("30000.00", Currency.MXN),
                    requested_term_months=24,
                    purpose="general_purpose",
                    idempotency_key=IdempotencyKey(f"idem-key-fixture-status-{index:04d}"),
                    created_at=SENT + timedelta(days=index),
                )
            )
            ids.append(application_id)
        await uow.commit()
    return ids


async def _tools(harness: Harness, customer: str, turn_id: str) -> list[str]:
    record = await harness.record(harness.session(customer), turn_id)
    return [call.tool.value for call in record.tool_calls]


async def test_es_mx_a_status_question_without_an_id_answers_the_one_intake(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    (application_id,) = await _seed(harness, MX, "MX-PL-STANDARD")
    reply = await harness.say("¿Cuál es el estado de mi solicitud de crédito?", harness.session(MX))
    assert (reply.state, reply.outcome) == ("RESOLVED", Outcome.RESOLVED)
    assert reply.response.template_id == "credit.application_status"
    text = reply.response.text
    assert f"Tu solicitud {application_id} de préstamo personal está registrada, en espera de revisión." in text
    assert approval_terms(text) == ()
    assert "list_my_credit_applications" in await _tools(harness, MX, reply.turn_id)
    record = await harness.record(harness.session(MX), reply.turn_id)
    assert record.grounding.violations == ()


async def test_pt_several_intakes_list_the_newest_three(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    ids = await _seed(harness, PT, "MX-PL-STANDARD", "MX-CC-CLASSIC", "MX-PL-STANDARD", "MX-CC-CLASSIC")
    reply = await harness.say("Qual é a situação da minha solicitação de crédito?", harness.session(PT))
    assert (reply.state, reply.outcome) == ("RESOLVED", Outcome.RESOLVED)
    assert reply.response.template_id == "credit.application_statuses"
    lines = reply.response.text.split("\n")
    assert lines[0] == "Estas são as suas solicitações mais recentes:"
    assert [line.split(",")[0] for line in lines[1:4]] == [ids[3], ids[2], ids[1]]
    assert lines[1].startswith(f"{ids[3]}, cartão de crédito, de ")
    assert lines[1].endswith(": registrada, aguardando análise")
    assert ids[0] not in reply.response.text
    assert approval_terms(reply.response.text) == ()


async def test_es_co_no_intake_says_none_is_on_record_and_offers_the_catalog(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    reply = await harness.say("¿Cuál es el estado de mi solicitud de crédito?", harness.session(CO))
    assert (reply.state, reply.outcome) == ("RESOLVED", Outcome.RESOLVED)
    assert reply.response.template_id == "credit.status_none_on_record"
    assert reply.response.text.startswith("No encontré solicitudes de crédito a tu nombre.")
    assert "list_my_credit_applications" in await _tools(harness, CO, reply.turn_id)


async def test_pt_no_intake_says_none_is_on_record(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    reply = await harness.say("Qual é a situação da minha solicitação de crédito?", harness.session(PT))
    assert reply.response.template_id == "credit.status_none_on_record"
    assert reply.response.text.startswith("Não encontrei solicitações de crédito em seu nome.")
