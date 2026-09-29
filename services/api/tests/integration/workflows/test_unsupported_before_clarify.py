"""A request an enabled workflow recognizes as unsupported is abstained before the workflow question (phase 14b,
found on the dev split): "Transfiere 2000 pesos de mi cuenta de ahorro a la corriente" was asked "saldos o
tarjetas", and after "saldos" P showed the balances instead of abstaining with ``ACC-ALL-3``."""

import pytest

from bank_agent.domain.workflow import Outcome
from bank_agent_scenarios import MX, PT
from bank_agent_workflow_support import Backend
from bank_agent_workflows import build_harness

TEXTS = {
    MX: "Transfiere 2000 pesos de mi cuenta de ahorro a la corriente",
    PT: "Transfira 2000 pesos da poupança para a conta corrente",
}


@pytest.mark.parametrize("customer", [MX, PT])
async def test_a_transfer_is_abstained_with_the_account_clause(backend: Backend, customer: str) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store)
    session = harness.session(customer)
    reply = await harness.say(TEXTS[customer], session)
    assert (reply.state, reply.outcome) == ("ABSTAINED", Outcome.ABSTAINED)
    assert "ACC-ALL-3@1" in [str(c.clause) for c in reply.response.citations]
    record = await harness.record(session, reply.turn_id)
    assert record.tool_calls == ()
