"""Property: whatever the tools do, a success message exists only with a positive verification record."""

import asyncio

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from bank_agent.adapters.persistence.memory.sessions import InMemorySessionStore
from bank_agent.adapters.persistence.memory.store import InMemoryStore
from bank_agent.adapters.persistence.memory.unit_of_work import InMemoryUnitOfWorkFactory
from bank_agent.domain.actions import ActionKind, ToolFailureMode, ToolName
from bank_agent.domain.conversation import ActionDisplayStatus, TurnResult
from bank_agent.domain.execution_record import ExecutionRecord
from bank_agent_scenarios import MX, scenario_data
from bank_agent_workflows import Harness, build_harness

MODES = st.one_of(st.none(), st.sampled_from(list(ToolFailureMode)))
SUCCESS_WORDS = ("registramos", "bloqueamos")


def _verified_tools(record: ExecutionRecord) -> set[str]:
    return {
        call.tool.value for call in record.tool_calls if call.verification is not None and call.verification.verified
    }


def check(result: TurnResult, record: ExecutionRecord) -> None:
    verified = _verified_tools(record)
    for status in result.response.action_statuses:
        if status.status is ActionDisplayStatus.VERIFIED:
            assert status.action.value in verified
    text = result.response.text.casefold()
    if "registramos" in text:
        assert ActionKind.CREATE_DISPUTE_CASE.value in verified
    if "bloqueamos" in text:
        assert ActionKind.BLOCK_CARD.value in verified


async def run(harness: Harness, block: bool) -> None:
    session = harness.session(MX, step_up=True)
    first = await harness.say("No reconozco un cargo de 1250 pesos en FIXTURE MARKET del 15 de junio", session)
    results = [first]
    results.append(await harness.say("sí" if block else "no", session, first.conversation_id))
    results.append(await harness.say("sí", session, first.conversation_id))
    for result in results:
        check(result, await harness.record(session, result.turn_id))


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(case_mode=MODES, block_mode=MODES, block=st.booleans())
def test_success_is_reported_only_after_a_positive_read_back(
    case_mode: ToolFailureMode | None, block_mode: ToolFailureMode | None, block: bool
) -> None:
    plan = {tool: mode for tool, mode in ((ToolName.CREATE_DISPUTE_CASE, case_mode), (ToolName.BLOCK_CARD, block_mode))
            if mode is not None}  # fmt: skip
    data = scenario_data()
    store = InMemoryStore()
    store.seed(customers=data.customers, products=data.products, transactions=data.transactions, cases=data.cases)
    harness = build_harness(InMemoryUnitOfWorkFactory(store), InMemorySessionStore(), failures=plan or None)
    asyncio.run(run(harness, block))
