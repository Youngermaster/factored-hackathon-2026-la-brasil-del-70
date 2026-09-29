"""A credit amount the customer stated in pesos is in the customer's own currency, whatever currency the model
guesses (phase 14b, found on the dev split): the local model said COP for a Mexican customer's "50.000 pesos", the
amount was dropped as a currency mismatch, and P asked for the amount again until it transferred the case."""

from bank_agent.testing.fake_llm import FakeLLM, ScriptedResponse
from bank_agent_scenarios import PT
from bank_agent_workflow_support import CREDIT_SLOTS, NO_SIGNALS, SIGNALS, Backend
from bank_agent_workflows import build_harness

GUESS = {"product_of_interest": "credit_card", "requested_amount": "30000", "currency_hint": "COP",
         "requested_term_months": None, "purpose": None, "declared_monthly_income": None}  # fmt: skip


async def test_a_guessed_currency_does_not_drop_the_stated_amount(backend: Backend) -> None:
    fake = FakeLLM()
    fake.script(SIGNALS, ScriptedResponse(output=NO_SIGNALS))
    fake.script(CREDIT_SLOTS, ScriptedResponse(output=GUESS))
    harness = build_harness(backend.uow_factory, backend.session_store, llm=fake)
    session = harness.session(PT, step_up=True)
    reply = await harness.say("Sou elegível para um cartão de crédito com limite de 30 mil pesos?", session)
    assert reply.state == "EXPLAIN_ELIGIBILITY"
