"""Baseline B1: the agent loop with a scripted model, its tools on its own database, and its end state."""

from typing import Any

from bank_evals_support import scenario

from bank_agent.domain.actions import ToolFailureMode, ToolName
from bank_agent.domain.errors import LlmProviderRejectedError
from bank_agent.domain.intelligence import PromptRef
from bank_agent.domain.locale import Language
from bank_agent.testing.fake_llm import FakeLLM, ScriptedError, ScriptedResponse
from bank_evals.scenarios.model import ToolFailureStep
from bank_evals.systems.naive_agent.agent import APOLOGY, NaiveAgentSystem
from bank_evals.systems.naive_agent.database import NaiveDatabase
from bank_evals.systems.naive_agent.tools import NaiveTools, render_result
from bank_evals.systems.schedule import FailureSchedule
from bank_evals.world import build_world

STEP = PromptRef(prompt_id="naive_agent_step", version=1)
ME, OTHER = "CLI-EVMX0002", "CLI-EVMX0013"


def step(
    action: str = "reply",
    tool: str | None = None,
    reply: str | None = "Listo.",
    outcome: str | None = "resolved",
    **arguments: str,
) -> ScriptedResponse:
    output: dict[str, Any] = {
        "action": action,
        "tool": tool,
        "arguments": arguments,
        "reply": reply,
        "outcome": outcome,
    }
    return ScriptedResponse(output=output)


async def test_b1_calls_a_tool_then_replies_and_records_every_call() -> None:
    fake = FakeLLM()
    fake.script(STEP, step("call_tool", "list_cards", None, None, customer_id=ME), step(reply="Tus tarjetas: 2."))
    case = await NaiveAgentSystem(fake, "fake/scripted").start(scenario(), build_world(), run_index=1)
    turn = await case.send("¿Qué tarjetas tengo?")
    assert (turn.outcome, turn.assistant_text) == ("resolved", "Tus tarjetas: 2.")
    assert [(c.tool, c.status, c.customer_id) for c in turn.tool_calls] == [("list_cards", "ok", ME)]
    assert len(turn.llm_calls) == 2
    assert "customer_id" in fake.calls[0].variables


async def test_b1_blocks_without_a_gate_and_its_transfer_escalates() -> None:
    fake = FakeLLM()
    fake.script(
        STEP,
        step("call_tool", "block_card", None, None, customer_id=ME, product_id="PRD-EVMX0002-01", reason="lost"),
        step(
            "call_tool", "transfer_to_human", None, None, customer_id=ME, reason="r", request="q", verified_facts="a; b"
        ),
        step(reply="Bloqueada y te paso con alguien.", outcome="escalated"),
    )
    case = await NaiveAgentSystem(fake, "fake/scripted").start(scenario(), build_world(), run_index=1)
    turn = await case.send("Bloquea mi tarjeta")
    end = await case.finish()
    assert turn.state == "ESCALATED"
    assert turn.claimed_actions == ["block_card"]
    assert end.product_statuses["PRD-EVMX0002-01"] == "blocked"
    assert end.writes == 1
    assert end.handoffs[0]["document"]["verified_facts"] == ["a", "b"]


async def test_a_model_failure_or_a_step_limit_ends_the_turn_with_an_apology() -> None:
    fake = FakeLLM()
    fake.script(STEP, ScriptedError(LlmProviderRejectedError))
    case = await NaiveAgentSystem(fake, "fake/scripted").start(scenario(), build_world(), run_index=1)
    turn = await case.send("Hola")
    assert (turn.outcome, turn.assistant_text) == ("in_progress", APOLOGY[Language.ES])
    looping = FakeLLM()
    looping.script(STEP, step("call_tool", "list_cards", None, None, customer_id=ME))
    case = await NaiveAgentSystem(looping, "fake/scripted").start(scenario(), build_world(), run_index=1)
    assert (await case.send("Hola")).assistant_text == APOLOGY[Language.ES]
    case.expire_session()
    await case.reauthenticate()
    await case.step_up()
    case.advance_clock(5)


def test_b1_tools_read_any_customer_the_model_names() -> None:
    tools = NaiveTools(NaiveDatabase(build_world().copy()), FailureSchedule(()))
    assert tools.call("get_balances", {"customer_id": OTHER})[0] == "ok"
    assert tools.call("list_transactions", {"customer_id": OTHER})[0] == "ok"
    assert tools.call("get_credit_profile", {"customer_id": "CLI-EVMX0008"})[1]["credit_score"] == 780
    assert tools.call("list_credit_products", {"country": "MX"})[0] == "ok"
    assert tools.call("get_statement", {"customer_id": "CLI-EVMX0001", "month": "2026-05"})[0] == "ok"
    assert tools.call("get_payment_status", {"customer_id": ME, "transaction_id": "TRX-EVMX0002-003"})[0] == "ok"
    assert tools.call("list_cases", {"customer_id": "CLI-EVMX0005"})[0] == "ok"
    assert tools.call("list_credit_applications", {"customer_id": "CLI-EVMX0012"})[0] == "ok"
    assert tools.call("get_balances", {"customer_id": "CLI-NOBODY"}) == ("not_found", None)
    assert tools.call("get_balances", {})[0] == "error"
    assert tools.call("drop_tables", {})[0] == "error"
    assert '"status": "ok"' in render_result("list_cards", "ok", [])


def test_b1_writes_follow_the_failure_plan() -> None:
    plan = (
        ToolFailureStep(tool=ToolName.CREATE_DISPUTE_CASE, mode=ToolFailureMode.TIMEOUT),
        ToolFailureStep(tool=ToolName.SUBMIT_CREDIT_APPLICATION, mode=ToolFailureMode.PARTIAL_WRITE),
    )
    db = NaiveDatabase(build_world().copy())
    tools = NaiveTools(db, FailureSchedule(plan))
    assert tools.call("create_dispute", {"customer_id": ME, "transaction_id": "TRX-EVMX0002-004"})[0] == "error"
    assert tools.call("create_dispute", {"customer_id": ME, "transaction_id": "TRX-EVMX0002-004"})[0] == "ok"
    status, _ = tools.call("submit_credit_application", {"customer_id": ME, "product_code": "MX-PL-STANDARD"})
    assert status == "ok"
    assert (len(db.new_cases), len(db.new_applications)) == (1, 0)
    assert tools.call("block_card", {"customer_id": ME, "product_id": "PRD-NOPE"}) == ("not_found", None)
