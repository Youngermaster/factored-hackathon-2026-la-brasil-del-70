from datetime import UTC, datetime, timedelta

import pytest

from bank_agent.domain.base import UntrustedText
from bank_agent.domain.identifiers import IdKind
from bank_agent.domain.intelligence import TransactionDescriptor
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Intent
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent.testing.language import FakeLanguageDetector
from bank_agent.testing.models import FakeIntentRouter, FakeTransactionResolver
from bank_agent.testing.telemetry import RecordingTelemetry
from bank_agent_builders import T0, transaction


def test_fixed_clock_moves_only_forward_and_only_when_told() -> None:
    clock = FixedClock(T0)
    assert clock.now() == T0
    assert clock.advance(timedelta(minutes=5)) == T0 + timedelta(minutes=5)
    clock.set(T0 + timedelta(hours=1))
    assert clock.now() == T0 + timedelta(hours=1)
    with pytest.raises(ValueError, match="backwards"):
        clock.advance(timedelta(seconds=-1))
    with pytest.raises(ValueError, match="backwards"):
        clock.set(T0)
    with pytest.raises(ValueError, match="timezone"):
        FixedClock(datetime(2026, 1, 1))  # noqa: DTZ001


def test_fixed_clock_normalizes_to_utc() -> None:
    from zoneinfo import ZoneInfo

    local = datetime(2026, 6, 10, 10, 0, tzinfo=ZoneInfo("America/Bogota"))
    assert FixedClock(local).now().tzinfo is UTC


def test_sequential_ids_count_per_kind() -> None:
    ids = SequentialIdGenerator()
    assert ids.new(IdKind.CASE) == "case-000001"
    assert ids.new(IdKind.CASE) == "case-000002"
    assert ids.new(IdKind.TURN) == "turn-000001"


def test_fake_language_detector_defaults_and_overrides() -> None:
    detector = FakeLanguageDetector()
    assert detector.detect(UntrustedText("hola")).language is Language.ES
    detector.set("oi, tudo bem", Language.PT, confidence=0.8)
    assert detector.detect(UntrustedText("oi, tudo bem")).language is Language.PT
    detector.set("hola, tudo bem", None, confidence=0.4, is_mixed=True)
    uncertain = detector.detect(UntrustedText("hola, tudo bem"))
    assert uncertain.language is None
    assert uncertain.is_mixed
    assert FakeLanguageDetector(default=None).detect(UntrustedText("x")).candidates == ()


def test_fake_router_scripts_and_threshold() -> None:
    router = FakeIntentRouter(threshold=0.6)
    router.set("quiero disputar", Intent.DISPUTE_NEW, 0.9)
    confident = router.route(UntrustedText("quiero disputar"), Language.ES)
    assert confident.intent is Intent.DISPUTE_NEW
    assert not confident.below_threshold
    assert router.route(UntrustedText("otra cosa"), Language.ES).below_threshold


def test_fake_resolver_ranks_and_picks_a_clear_winner() -> None:
    first = transaction("T1", occurred_at=T0 - timedelta(days=2))
    second = transaction("T2", occurred_at=T0 - timedelta(days=1))
    resolver = FakeTransactionResolver({"T1": 0.9, "T2": 0.3})
    resolution = resolver.rank(TransactionDescriptor(), [second, first], now=T0)
    assert [c.transaction_id for c in resolution.ranked] == ["T1", "T2"]
    assert resolution.clear_winner == "T1"
    tied = FakeTransactionResolver().rank(TransactionDescriptor(), [first, second], now=T0)
    assert [c.transaction_id for c in tied.ranked] == ["T2", "T1"]
    assert tied.clear_winner is None
    assert FakeTransactionResolver().rank(TransactionDescriptor(), [], now=T0).margin is None


def test_recording_telemetry_keeps_spans_and_metrics() -> None:
    telemetry = RecordingTelemetry()
    with telemetry.span("turn", {"state": "START"}) as span:
        span.set_attribute("outcome", "resolved")
        span.record_error_code("tool_timeout")
    telemetry.counter("escalations").add(2, {"reason": "tool_failure"})
    telemetry.histogram("turn_ms").record(12.5)
    assert telemetry.spans[0].attributes == {"state": "START", "outcome": "resolved"}
    assert telemetry.spans[0].error_codes == ["tool_timeout"]
    assert telemetry.counter("escalations").total == 2
    assert telemetry.histogram("turn_ms").values == [(12.5, {})]
