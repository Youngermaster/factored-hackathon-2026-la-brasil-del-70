"""The guarded toolset: the per-state allowlist, bounded retries for transient failures only, and records."""

import asyncio

import pytest

from bank_agent.application.engine.recorder import TurnRecorder
from bank_agent.application.engine.tools import GuardedToolset
from bank_agent.domain.actions import ToolName, Verification
from bank_agent.domain.errors import (
    ToolNotAllowedError,
    ToolPermanentError,
    ToolTimeoutError,
    TransactionNotFoundError,
)
from bank_agent.domain.execution_record import ToolCallStatus
from bank_agent.domain.identifiers import SourceRef, TransactionId
from bank_agent.testing.telemetry import RecordingTelemetry
from bank_agent_builders import T0


class Flaky:
    """A toolset stand-in whose ``get_transaction`` fails a set number of times first."""

    def __init__(self, failures: int, error: type[Exception] = ToolTimeoutError) -> None:
        self.failures, self.error, self.calls = failures, error, 0

    async def get_transaction(self, transaction_id: TransactionId) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error("fixture failure")
        return f"found {transaction_id}"


def guarded(inner: object, budget: int = 2) -> tuple[GuardedToolset, TurnRecorder]:
    recorder = TurnRecorder(monotonic=lambda: 0.0)
    tools = GuardedToolset(inner, recorder, retry_budget=budget, monotonic=lambda: 0.0)  # type: ignore[arg-type]
    return tools, recorder


async def test_a_tool_outside_the_allowlist_is_recorded_and_refused() -> None:
    tools, recorder = guarded(Flaky(0))
    with pytest.raises(ToolNotAllowedError):
        await tools.get_transaction(TransactionId("TXN-1"))
    assert recorder.tool_calls[0].status is ToolCallStatus.REJECTED_BY_ALLOWLIST
    assert recorder.safety == ["tool_rejected_by_allowlist"]


async def test_transient_failures_are_retried_within_the_budget() -> None:
    inner = Flaky(2)
    tools, recorder = guarded(inner)
    tools.allow(frozenset({ToolName.GET_TRANSACTION}))
    assert str(await tools.get_transaction(TransactionId("TXN-1"))) == "found TXN-1"
    call = recorder.tool_calls[0]
    assert (call.status, call.attempts, call.arguments) == (ToolCallStatus.OK, 3, {"transaction_id": "[redacted]"})


async def test_the_budget_bounds_retries_and_the_failure_is_recorded() -> None:
    inner = Flaky(5)
    tools, recorder = guarded(inner)
    tools.allow(frozenset({ToolName.GET_TRANSACTION}))
    with pytest.raises(ToolTimeoutError):
        await tools.get_transaction(TransactionId("TXN-1"))
    assert inner.calls == 3
    assert (recorder.tool_calls[0].status, recorder.tool_calls[0].error_code) == (ToolCallStatus.FAILED, "tool_timeout")


@pytest.mark.parametrize(
    ("error", "status"),
    [(ToolPermanentError, ToolCallStatus.FAILED), (TransactionNotFoundError, ToolCallStatus.NOT_FOUND)],
)
async def test_other_failures_are_never_retried(error: type[Exception], status: ToolCallStatus) -> None:
    inner = Flaky(1, error)
    tools, recorder = guarded(inner)
    tools.allow(frozenset({ToolName.GET_TRANSACTION}))
    with pytest.raises(error):
        await tools.get_transaction(TransactionId("TXN-1"))
    assert (inner.calls, recorder.tool_calls[0].status) == (1, status)


async def test_engine_checks_widen_the_allowlist_only_inside_the_block() -> None:
    tools, recorder = guarded(Flaky(0))
    with tools.engine_check(frozenset({ToolName.GET_TRANSACTION})):
        await tools.get_transaction(TransactionId("TXN-1"))
    assert tools.allowed == frozenset()
    verification = Verification(
        verified=True, check="fixture", evidence=SourceRef.model_validate("transactions:TXN-1"), checked_at=T0
    )
    tools.attach_verification(ToolName.GET_TRANSACTION, verification)
    assert recorder.tool_calls[0].verification == verification


class Slow:
    """A toolset stand-in whose ``get_transaction`` takes longer than any timeout the tests set."""

    def __init__(self) -> None:
        self.calls = 0

    async def get_transaction(self, transaction_id: TransactionId) -> str:
        self.calls += 1
        await asyncio.sleep(10)
        return f"found {transaction_id}"


async def test_a_slow_tool_times_out_is_retried_and_is_recorded_as_a_timeout() -> None:
    inner = Slow()
    recorder = TurnRecorder(monotonic=lambda: 0.0)
    tools = GuardedToolset(inner, recorder, retry_budget=1, monotonic=lambda: 0.0, timeout_seconds=0.01)  # type: ignore[arg-type]
    tools.allow(frozenset({ToolName.GET_TRANSACTION}))
    with pytest.raises(ToolTimeoutError):
        await tools.get_transaction(TransactionId("TXN-1"))
    assert inner.calls == 2
    call = recorder.tool_calls[0]
    assert (call.status, call.attempts, call.error_code) == (ToolCallStatus.FAILED, 2, "tool_timeout")


async def test_each_call_is_a_span_with_its_status_and_attempts() -> None:
    telemetry = RecordingTelemetry()
    recorder = TurnRecorder(monotonic=lambda: 0.0)
    tools = GuardedToolset(Flaky(1), recorder, retry_budget=2, monotonic=lambda: 0.0, telemetry=telemetry)  # type: ignore[arg-type]
    tools.allow(frozenset({ToolName.GET_TRANSACTION}))
    await tools.get_transaction(TransactionId("TXN-1"))
    tools.allow(frozenset())
    with pytest.raises(ToolNotAllowedError):
        await tools.get_transaction(TransactionId("TXN-1"))
    ok, refused = telemetry.spans
    assert (ok.name, ok.attributes) == (
        "bank.tool.call",
        {"bank.tool": "get_transaction", "bank.tool.status": "ok", "bank.tool.attempts": 2},
    )
    assert refused.attributes["bank.tool.status"] == "rejected_by_allowlist"
    assert refused.error_codes == [ToolNotAllowedError.code]
