"""Account inquiry scenarios 19 to 23 with language variants: balances, payment status, statements, unsupported
requests, and a contested balance, on the in-memory adapters and PostgreSQL."""

from pydantic import JsonValue

from bank_agent.domain.workflow import Outcome, WorkflowRef
from bank_agent.testing.fake_llm import FakeLLM, ScriptedResponse
from bank_agent_scenarios import AR, CO, MX, PT
from bank_agent_workflow_support import (
    ACCOUNT_SLOTS,
    NO_SIGNALS,
    SIGNALS,
    Backend,
    assert_no_transcript,
    assert_schema_valid,  # fmt: skip
)
from bank_agent_workflows import build_harness

ACCOUNT = WorkflowRef(id="account_inquiry", version=1)


async def test_19_es_ar_balances_state_the_as_of_date_in_the_account_currency(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(AR)
    reply = await harness.say("Hola, ¿me decís cuál es mi saldo?", session)
    assert (reply.state, reply.outcome) == ("BALANCES", Outcome.RESOLVED)
    text = reply.response.text
    assert "con datos al 17 de junio de 2026" in text
    assert "250.000,00 ARS" in text
    assert "45.000,00 ARS" in text
    assert "crédito disponible 255.000,00 ARS" in text
    assert reply.response.balances
    assert {balance.product_ref.table.value for balance in reply.response.balances} == {"products"}
    assert "ACC-ALL-1@1" in [str(c.clause) for c in reply.response.citations]
    record = await harness.record(session, reply.turn_id)
    assert record.workflow == ACCOUNT
    assert record.grounding.violations == ()
    assert any(r.rule_id == "ACC.as_of_disclosed" and r.passed for d in record.decisions for r in d.rule_results)
    assert {call.tool.value for call in record.tool_calls} == {"list_my_balances"}


async def test_19b_pt_br_balance_with_the_model_extraction_scripted(backend: Backend) -> None:
    fake = FakeLLM()
    fake.script(SIGNALS, ScriptedResponse(output=NO_SIGNALS))
    slots: dict[str, JsonValue] = {"product_hint": {"product_type": "savings_account", "last4": None},
             "statement_period_expression": None, "payment": None}  # fmt: skip
    fake.script(ACCOUNT_SLOTS, ScriptedResponse(output=slots))
    harness = build_harness(backend.uow_factory, backend.session_store, llm=fake)
    session = harness.session(PT)
    reply = await harness.say("Qual é o saldo da minha conta, por favor?", session)
    assert (reply.state, reply.outcome) == ("BALANCES", Outcome.RESOLVED)
    assert "Estes são os seus saldos, com dados de 17 de junho de 2026" in reply.response.text
    assert "conta poupança **** 4444: saldo 18.000,00 MXN" in reply.response.text
    record = await harness.record(session, reply.turn_id)
    assert [str(call.prompt) for call in record.llm_calls] == [
        "detect_escalation_signals@1", "extract_account_inquiry_slots@1",
    ]  # fmt: skip


async def test_20_pt_br_two_similar_transfers_are_clarified_then_answered(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT)
    asked = await harness.say("Qual é a situação da minha transferência de 1500 pesos?", session)
    assert (asked.state, asked.outcome) == ("CLARIFY", Outcome.CLARIFIED)
    assert "1) 15 de junho de 2026, JOAO PEREIRA, 1.500,00 MXN" in asked.response.text
    assert "2) 12 de junho de 2026, JOAO PEREIRA, 1.500,00 MXN" in asked.response.text
    answered = await harness.say("a primeira", session, asked.conversation_id)
    assert (answered.state, answered.outcome) == ("PAYMENT_STATUS", Outcome.RESOLVED)
    assert "Situação da sua transferência de 1.500,00 MXN de 15 de junho de 2026" in answered.response.text
    assert ": pendente. Dados de 17 de junho de 2026." in answered.response.text
    (payment,) = answered.response.payment_statuses
    assert (payment.status.value, str(payment.amount.amount)) == ("pending", "1500.00")
    record = await harness.record(session, answered.turn_id)
    assert "get_payment_status" in [call.tool.value for call in record.tool_calls]
    assert record.grounding.violations == ()


async def test_21_es_mx_statement_for_last_month_has_totals_and_no_balances(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    reply = await harness.say("Quiero el estado de cuenta de mi tarjeta de crédito del mes pasado", session)
    assert (reply.state, reply.outcome) == ("STATEMENT_SUMMARY", Outcome.RESOLVED)
    text = reply.response.text
    assert "del 1 de mayo de 2026 al 31 de mayo de 2026, con datos al 17 de junio de 2026" in text
    assert "Operaciones en el periodo: 4." in text
    assert "Totales en MXN: cargos 1,550.00 MXN; abonos 1,500.00 MXN." in text
    assert "Pendientes, rechazadas o revertidas: 1." in text
    assert "saldo" not in text.split("\n\n")[0].lower()
    assert reply.response.statement is not None
    assert reply.response.statement.transaction_count == 4
    record = await harness.record(session, reply.turn_id)
    assert record.grounding.violations == ()
    assert any(r.rule_id == "ACC.statement_period_within_limit" and r.passed
               for d in record.decisions for r in d.rule_results)  # fmt: skip


async def test_21b_es_mx_a_period_over_the_limit_is_asked_again(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(MX)
    first = "Quiero un resumen de mi tarjeta de crédito de los últimos seis meses"
    asked = await harness.say(first, session)
    assert (asked.state, asked.outcome) == ("STATEMENT_PERIOD", Outcome.CLARIFIED)
    assert "más largo de lo que puedo resumir" in asked.response.text
    assert "ACC-ALL-2@1" in [str(c.clause) for c in asked.response.citations]
    answered = await harness.say("el mes pasado", session, asked.conversation_id)
    assert answered.state == "STATEMENT_SUMMARY"


async def test_22_pt_br_a_transfer_is_abstained_with_the_acc_clause(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT)
    reply = await harness.say("Quero fazer uma transferência de 500 pesos para o João", session)
    assert (reply.state, reply.outcome) == ("ABSTAINED", Outcome.ABSTAINED)
    assert "pessoa da equipe" in reply.response.text
    cited = [str(c.clause) for c in reply.response.citations]
    assert "ACC-ALL-3@1" in cited
    assert "SCOPE-ALL-2@1" in cited
    record = await harness.record(session, reply.turn_id)
    assert record.workflow == ACCOUNT
    assert "unsupported_transfer" in record.safety_interventions
    assert record.tool_calls == ()


async def test_22b_es_co_a_bill_payment_is_abstained_with_the_acc_clause(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(CO)
    reply = await harness.say("Quiero pagar mi tarjeta de crédito desde aquí", session)
    assert (reply.state, reply.outcome) == ("ABSTAINED", Outcome.ABSTAINED)
    assert "persona del equipo" in reply.response.text
    assert "ACC-ALL-3@1" in [str(c.clause) for c in reply.response.citations]


async def test_23_es_co_a_contested_balance_escalates_with_the_balance_as_a_fact(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(CO)
    shown = await harness.say("¿Cuál es el saldo de mi cuenta?", session)
    assert shown.state == "BALANCES"
    text = "Ese saldo está mal, no es correcto"
    reply = await harness.say(text, session, shown.conversation_id)
    assert (reply.state, reply.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert reply.response.escalation is not None
    handoff = (await harness.handoff(session, reply.response.escalation.handoff_id)).handoff
    assert_schema_valid(handoff)
    assert_no_transcript(handoff, text)
    assert handoff.escalation_reason.code.value == "unsupported_needs_human"
    facts = [fact.fact for fact in handoff.verified_facts]
    assert "checking_account ending 3333 balance 3450000.00 COP as of 2026-06-17" in facts
    assert handoff.open_questions


async def test_23b_pt_br_a_contested_balance_escalates(backend: Backend) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(PT)
    reply = await harness.say("O saldo da minha conta está errado", session)
    assert (reply.state, reply.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert "pessoa da equipe" in reply.response.text
    assert reply.response.escalation is not None
    handoff = (await harness.handoff(session, reply.response.escalation.handoff_id)).handoff
    assert handoff.language.value == "pt"
    assert any("savings_account ending 4444" in fact.fact for fact in handoff.verified_facts)
