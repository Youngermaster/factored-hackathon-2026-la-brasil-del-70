"""Contract suites for the intelligence and determinism ports.

They run against the test doubles and every production adapter: the keyword and learned routers, the rule and
ranking resolvers (learned ones from small hand-written artifacts in a temporary registry), and the filesystem
model registry.
"""

import re
import tempfile
from collections.abc import Callable
from datetime import UTC, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from bank_agent.adapters.models.embedding_router import EmbeddingIntentRouter
from bank_agent.adapters.models.keyword_router import KeywordIntentRouter
from bank_agent.adapters.models.lgbm_resolver import LgbmTransactionResolver
from bank_agent.adapters.models.registry import FilesystemModelRegistry, FilesystemModelStore
from bank_agent.adapters.models.rules_resolver import RuleTransactionResolver
from bank_agent.adapters.models.tfidf_router import TfidfIntentRouter
from bank_agent.adapters.system.clock import SystemClock
from bank_agent.adapters.system.ids import RandomIdGenerator
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import ModelArtifactIntegrityError, ModelArtifactNotFoundError
from bank_agent.domain.identifiers import ID_PATTERN, IdKind
from bank_agent.domain.intelligence import TransactionDescriptor
from bank_agent.domain.locale import Language
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.models import IntentRouter, LanguageDetector, ModelRegistry, TransactionResolver
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent.testing.language import FakeLanguageDetector
from bank_agent.testing.models import FakeIntentRouter, FakeTransactionResolver
from bank_agent_builders import T0, transaction
from bank_agent_models import EMBEDDING_ARTIFACT, LGBM_ARTIFACT, TFIDF_ARTIFACT, FixtureEmbedder, publish


def _temporary_registry() -> Path:
    return Path(tempfile.mkdtemp(prefix="model-registry-"))


def _tfidf() -> IntentRouter:
    return TfidfIntentRouter.load(publish(_temporary_registry(), "router:tfidf", TFIDF_ARTIFACT))


def _embeddings() -> IntentRouter:
    return EmbeddingIntentRouter.load(
        publish(_temporary_registry(), "router:embeddings", EMBEDDING_ARTIFACT), FixtureEmbedder()
    )


def _lgbm() -> TransactionResolver:
    return LgbmTransactionResolver.load(publish(_temporary_registry(), "resolver:lgbm", LGBM_ARTIFACT))


ROUTERS = [
    pytest.param(FakeIntentRouter, marks=pytest.mark.unit, id="fake"),
    pytest.param(KeywordIntentRouter, marks=pytest.mark.unit, id="keyword"),
    pytest.param(_tfidf, marks=pytest.mark.unit, id="tfidf"),
    pytest.param(_embeddings, marks=pytest.mark.unit, id="embeddings"),
]
RESOLVERS = [
    pytest.param(lambda: FakeTransactionResolver({"T2": 0.9}), marks=pytest.mark.unit, id="fake"),
    pytest.param(RuleTransactionResolver, marks=pytest.mark.unit, id="rules"),
    pytest.param(_lgbm, marks=pytest.mark.unit, id="lgbm"),
]
REGISTRIES = [
    pytest.param(
        lambda root: (FilesystemModelStore(root), FilesystemModelRegistry(root)), marks=pytest.mark.unit, id="fs"
    )
]
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
        for descriptor in (TransactionDescriptor(), TransactionDescriptor(amount=Decimal("1250"))):
            resolution = factory().rank(descriptor, [*candidates, candidates[0]], now=T0)
            ranked = [candidate.transaction_id for candidate in resolution.ranked]
            assert set(ranked) <= {"T1", "T2", "T3"}
            assert len(ranked) == len(set(ranked))
            assert [candidate.rank for candidate in resolution.ranked] == list(range(1, len(ranked) + 1))
            if resolution.clear_winner is not None:
                assert resolution.clear_winner == ranked[0]

    def test_a_matching_description_ranks_the_match(self, factory: Callable[[], TransactionResolver]) -> None:
        wanted = transaction("T2", amount="777.00", occurred_at=T0 - timedelta(days=1))
        resolution = factory().rank(TransactionDescriptor(amount=Decimal("777")), [transaction("T1"), wanted], now=T0)
        assert resolution.ranked
        assert resolution.ranked[0].transaction_id == "T2"

    def test_no_candidates_yield_an_empty_ranking(self, factory: Callable[[], TransactionResolver]) -> None:
        resolution = factory().rank(TransactionDescriptor(), [], now=T0)
        assert resolution.ranked == ()
        assert resolution.clear_winner is None


@pytest.mark.parametrize("factory", REGISTRIES)
class TestModelRegistryContract:
    def test_resolves_versions_and_aliases_with_a_verified_digest(
        self, factory: Callable[[Path], tuple[FilesystemModelStore, ModelRegistry]], tmp_path: Path
    ) -> None:
        store, registry = factory(tmp_path)
        stored = store.register("router:tfidf", TFIDF_ARTIFACT, {"metrics": {"macro_f1": 0.9}})
        store.set_alias("router:tfidf", "champion", stored.ref.version, {"approved_by": "contract"})
        by_alias = registry.resolve("router:tfidf", "champion")
        by_version = registry.resolve("router:tfidf", stored.ref.version)
        assert by_alias == by_version
        assert str(by_alias.ref) == f"router:tfidf@{stored.ref.version}"
        assert re.fullmatch(r"[0-9a-f]{64}", by_alias.sha256)
        assert Path(by_alias.local_path).is_file()

    def test_unknown_names_and_tampered_files_raise_typed_errors(
        self, factory: Callable[[Path], tuple[FilesystemModelStore, ModelRegistry]], tmp_path: Path
    ) -> None:
        store, registry = factory(tmp_path)
        with pytest.raises(ModelArtifactNotFoundError):
            registry.resolve("resolver:lgbm", "champion")
        stored = store.register("resolver:lgbm", LGBM_ARTIFACT, {})
        Path(stored.local_path).write_text("{}")
        with pytest.raises(ModelArtifactIntegrityError):
            registry.resolve("resolver:lgbm", stored.ref.version)


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
