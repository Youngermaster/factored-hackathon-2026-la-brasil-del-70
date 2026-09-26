"""Contract suites for the intelligence and determinism ports.

They run against the test doubles and the production system adapters now; phases 09 and 10 add the keyword
and learned routers, the rule and ranking resolvers, and the lingua detector to the same parameter lists.
"""

import re
from collections.abc import Callable
from datetime import UTC, timedelta

import pytest

from bank_agent.adapters.system.clock import SystemClock
from bank_agent.adapters.system.ids import RandomIdGenerator
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.identifiers import ID_PATTERN, IdKind
from bank_agent.domain.intelligence import TransactionDescriptor
from bank_agent.domain.locale import Language
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.models import IntentRouter, LanguageDetector, TransactionResolver
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent.testing.language import FakeLanguageDetector
from bank_agent.testing.models import FakeIntentRouter, FakeTransactionResolver
from bank_agent_builders import T0, transaction

ROUTERS = [pytest.param(FakeIntentRouter, marks=pytest.mark.unit, id="fake")]
RESOLVERS = [pytest.param(lambda: FakeTransactionResolver({"T2": 0.9}), marks=pytest.mark.unit, id="fake")]
DETECTORS = [pytest.param(FakeLanguageDetector, marks=pytest.mark.unit, id="fake")]
CLOCKS = [
    pytest.param(SystemClock, marks=pytest.mark.unit, id="system"),
    pytest.param(lambda: FixedClock(T0), marks=pytest.mark.unit, id="fixed"),
]
ID_GENERATORS = [
    pytest.param(RandomIdGenerator, marks=pytest.mark.unit, id="random"),
    pytest.param(SequentialIdGenerator, marks=pytest.mark.unit, id="sequential"),
]


@pytest.mark.parametrize("factory", ROUTERS)
class TestIntentRouterContract:
    def test_returns_a_versioned_prediction_within_bounds(self, factory: Callable[[], IntentRouter]) -> None:
        prediction = factory().route(UntrustedText("no reconozco un cargo"), Language.ES)
        assert 0.0 <= prediction.confidence <= 1.0
        assert prediction.model.version
        assert all(0.0 <= candidate.score <= 1.0 for candidate in prediction.candidates)


@pytest.mark.parametrize("factory", RESOLVERS)
class TestTransactionResolverContract:
    def test_ranks_only_the_given_candidates_each_once(self, factory: Callable[[], TransactionResolver]) -> None:
        candidates = [transaction("T1"), transaction("T2", occurred_at=T0 - timedelta(days=1)), transaction("T3")]
        resolution = factory().rank(TransactionDescriptor(), candidates, now=T0)
        ranked = [candidate.transaction_id for candidate in resolution.ranked]
        assert sorted(ranked) == ["T1", "T2", "T3"]
        assert [candidate.rank for candidate in resolution.ranked] == [1, 2, 3]
        if resolution.clear_winner is not None:
            assert resolution.clear_winner == ranked[0]

    def test_no_candidates_yield_an_empty_ranking(self, factory: Callable[[], TransactionResolver]) -> None:
        resolution = factory().rank(TransactionDescriptor(), [], now=T0)
        assert resolution.ranked == ()
        assert resolution.clear_winner is None


@pytest.mark.parametrize("factory", DETECTORS)
class TestLanguageDetectorContract:
    def test_returns_a_detection_with_a_versioned_detector(self, factory: Callable[[], LanguageDetector]) -> None:
        detection = factory().detect(UntrustedText("hola, quiero reclamar un cargo"))
        assert 0.0 <= detection.confidence <= 1.0
        assert detection.detector.version
        if detection.language is None:
            assert detection.confidence < 1.0


@pytest.mark.parametrize("factory", CLOCKS)
class TestClockContract:
    def test_returns_utc_and_never_goes_backwards(self, factory: Callable[[], Clock]) -> None:
        clock = factory()
        first = clock.now()
        second = clock.now()
        assert first.tzinfo is UTC
        assert second >= first


@pytest.mark.parametrize("factory", ID_GENERATORS)
class TestIdGeneratorContract:
    def test_ids_are_unique_prefixed_and_valid(self, factory: Callable[[], IdGenerator]) -> None:
        generator = factory()
        values = [generator.new(kind) for kind in IdKind for _ in range(20)]
        assert len(values) == len(set(values))
        for value in values:
            assert re.fullmatch(ID_PATTERN, value)
            assert len(value) <= 64
        assert generator.new(IdKind.CASE).startswith("case-")
