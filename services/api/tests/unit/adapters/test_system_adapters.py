import re
from datetime import UTC, datetime

import pytest

from bank_agent.adapters.system import clock as clock_module
from bank_agent.adapters.system.clock import SystemClock
from bank_agent.adapters.system.ids import RandomIdGenerator
from bank_agent.adapters.telemetry.noop import NoopTelemetry
from bank_agent.domain.identifiers import ID_PATTERN, IdKind


def test_system_clock_is_utc() -> None:
    assert SystemClock().now().tzinfo is UTC


def test_system_clock_never_goes_backwards(monkeypatch: pytest.MonkeyPatch) -> None:
    instants = iter([datetime(2026, 6, 10, 12, tzinfo=UTC), datetime(2026, 6, 10, 11, tzinfo=UTC)])

    class _SteppingDatetime:
        @staticmethod
        def now(tz: object) -> datetime:
            return next(instants)

    monkeypatch.setattr(clock_module, "datetime", _SteppingDatetime)
    clock = SystemClock()
    first = clock.now()
    assert clock.now() == first


def test_random_ids_are_prefixed_unique_and_valid() -> None:
    ids = RandomIdGenerator()
    values = {ids.new(IdKind.CASE) for _ in range(200)}
    assert len(values) == 200
    for value in values:
        assert value.startswith("case-")
        assert re.fullmatch(ID_PATTERN, value)
        assert len(value) <= 64


def test_noop_telemetry_accepts_everything_and_records_nothing() -> None:
    telemetry = NoopTelemetry()
    with telemetry.span("turn", {"state": "START"}) as span:
        span.set_attribute("k", 1)
        span.record_error_code("tool_timeout")
        assert span.trace_id is None
    telemetry.counter("c").add(1)
    telemetry.histogram("h").record(1.0, {"a": True})
