"""Router models: two baselines and two learned models, all predicting through the same interface.

- ``majority``: the most frequent train intent, with its train share as confidence.
- ``keyword@1``: the shipped rule baseline (``bank_agent.adapters.models.keyword_router``) with its own threshold.
- ``tfidf``: scikit-learn ``TfidfVectorizer`` over the shared analyzer (``router_terms``) and a multinomial logistic
  regression; C is chosen on dev by macro-F1. The parameters are exported to a ``tfidf_logreg/1`` artifact and every
  prediction afterwards goes through the ``bank_agent`` adapter, so what is evaluated is what serves.
- ``embeddings``: multilingual-e5-small sentence embeddings (the ``ml`` extra) with a logistic regression head,
  exported to ``embedding_logreg/1`` and evaluated through its adapter.

For both learned models a temperature is fitted on dev and the abstention threshold is chosen on dev only.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from bank_agent.adapters.models.embedding_router import EmbeddingIntentRouter, EmbeddingRouterArtifact
from bank_agent.adapters.models.keyword_router import KeywordIntentRouter
from bank_agent.adapters.models.text_features import ANALYZER_ID, router_terms
from bank_agent.adapters.models.tfidf_router import TfidfIntentRouter, TfidfRouterArtifact
from bank_agent.adapters.retrieval.embedding import Embedder
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.intelligence import ModelComponent, ModelRef
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Intent
from bank_ml.common.calibration import fit_temperature, softmax
from bank_ml.common.metrics import encode, macro_f1
from bank_ml.common.seeds import seed_for
from bank_ml.common.thresholds import ThresholdChoice, choose_threshold
from bank_ml.router.augment import Item

C_GRID = (0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0)
TARGET_RISK = 0.05
MIN_DF = 2
DIGITS = 6
UNFITTED = ModelRef(component=ModelComponent.ROUTER, name="unfitted", version="0")


@dataclass(frozen=True)
class Predictions:
    intents: list[Intent]
    confidence: np.ndarray
    below_threshold: np.ndarray


class RouterModel(Protocol):
    name: str

    def predict(self, items: Sequence[Item]) -> Predictions: ...


def _language(item: Item) -> Language:
    return Language.PT if item.language == "pt" else Language.ES


class RoutePredictor:
    """Wraps any ``IntentRouter`` (baseline or loaded adapter) for batch evaluation."""

    def __init__(self, name: str, router: Any) -> None:
        self.name = name
        self._router = router

    def predict(self, items: Sequence[Item]) -> Predictions:
        routed = [self._router.route(UntrustedText(item.text), _language(item)) for item in items]
        return Predictions(
            [prediction.intent for prediction in routed],
            np.array([prediction.confidence for prediction in routed], dtype=np.float64),
            np.array([prediction.below_threshold for prediction in routed], dtype=bool),
        )


class MajorityBaseline:
    name = "majority"

    def __init__(self, train: Sequence[Item]) -> None:
        counts = Counter(item.intent for item in train)
        self.intent, top = min(counts.items(), key=lambda pair: (-pair[1], pair[0].value))
        self.share = top / len(train)

    def predict(self, items: Sequence[Item]) -> Predictions:
        size = len(items)
        return Predictions([self.intent] * size, np.full(size, self.share), np.zeros(size, dtype=bool))


def keyword_baseline() -> RoutePredictor:
    return RoutePredictor("keyword@1", KeywordIntentRouter())


@dataclass(frozen=True)
class Fitted:
    artifact: dict[str, Any]
    params: dict[str, Any]
    threshold: ThresholdChoice


def _labels(items: Sequence[Item], classes: Sequence[Intent]) -> np.ndarray:
    return encode([item.intent for item in items], list(classes))


def _calibrate(logits: np.ndarray, dev: Sequence[Item], classes: Sequence[Intent]) -> tuple[float, ThresholdChoice]:
    labels = _labels(dev, classes)
    temperature = fit_temperature(logits, labels)
    probabilities = softmax(logits, temperature)
    correct = probabilities.argmax(axis=1) == labels
    return temperature, choose_threshold(probabilities.max(axis=1), correct, TARGET_RISK)


def _pick_c(features_train: Any, y_train: np.ndarray, features_dev: Any, y_dev: np.ndarray, size: int) -> float:
    scores = []
    for c in C_GRID:
        model = LogisticRegression(C=c, max_iter=5000, random_state=seed_for("router", "logreg"))
        model.fit(features_train, y_train)
        scores.append((macro_f1(y_dev, model.predict(features_dev).astype(np.int64), size), -c, c))
    return max(scores)[2]


def fit_tfidf(train: Sequence[Item], dev: Sequence[Item], c: float | None = None) -> Fitted:
    classes = sorted({item.intent for item in train}, key=lambda intent: intent.value)
    vectorizer = TfidfVectorizer(analyzer=router_terms, sublinear_tf=True, min_df=MIN_DF, norm="l2", dtype=np.float64)
    x_train = vectorizer.fit_transform([item.text for item in train])
    x_dev = vectorizer.transform([item.text for item in dev])
    y_train, y_dev = _labels(train, classes), _labels(dev, classes)
    chosen = c if c is not None else _pick_c(x_train, y_train, x_dev, y_dev, len(classes))
    model = LogisticRegression(C=chosen, max_iter=5000, random_state=seed_for("router", "logreg"))
    model.fit(x_train, y_train)
    vocabulary = sorted(vectorizer.vocabulary_, key=vectorizer.vocabulary_.__getitem__)
    artifact: dict[str, Any] = {
        "format": "tfidf_logreg/1",
        "analyzer": ANALYZER_ID,
        "classes": [intent.value for intent in classes],
        "vocabulary": vocabulary,
        "idf": [round(float(value), DIGITS) for value in vectorizer.idf_],
        "weights": [[round(float(value), DIGITS) for value in row] for row in model.coef_.T],
        "intercept": [round(float(value), DIGITS) for value in model.intercept_],
        "temperature": 1.0,
        "threshold": 0.0,
    }
    router = TfidfIntentRouter(TfidfRouterArtifact.model_validate(artifact), UNFITTED)
    logits = np.array([router.logits(item.text) for item in dev])
    temperature, threshold = _calibrate(logits, dev, classes)
    artifact.update(temperature=temperature, threshold=round(threshold.threshold, DIGITS))
    params = {"C": chosen, "min_df": MIN_DF, "vocabulary_size": len(vocabulary), "temperature": temperature}
    return Fitted(artifact, params, threshold)


def fit_embeddings(train: Sequence[Item], dev: Sequence[Item], embedder: Embedder) -> Fitted:
    classes = sorted({item.intent for item in train}, key=lambda intent: intent.value)
    x_train = np.array([embedder.embed_query(item.text) for item in train])
    x_dev = np.array([embedder.embed_query(item.text) for item in dev])
    y_train, y_dev = _labels(train, classes), _labels(dev, classes)
    chosen = _pick_c(x_train, y_train, x_dev, y_dev, len(classes))
    model = LogisticRegression(C=chosen, max_iter=5000, random_state=seed_for("router", "logreg"))
    model.fit(x_train, y_train)
    artifact: dict[str, Any] = {
        "format": "embedding_logreg/1",
        "embedder": embedder.model_id,
        "classes": [intent.value for intent in classes],
        "weights": [[round(float(value), DIGITS) for value in row] for row in model.coef_],
        "intercept": [round(float(value), DIGITS) for value in model.intercept_],
        "temperature": 1.0,
        "threshold": 0.0,
    }
    router = EmbeddingIntentRouter(EmbeddingRouterArtifact.model_validate(artifact), embedder, UNFITTED)
    logits = np.array([router.logits_for(vector) for vector in x_dev])
    temperature, threshold = _calibrate(logits, dev, classes)
    artifact.update(temperature=temperature, threshold=round(threshold.threshold, DIGITS))
    params = {
        "C": chosen,
        "embedder": embedder.model_id,
        "dimensions": int(x_train.shape[1]),
        "temperature": temperature,
    }
    return Fitted(artifact, params, threshold)
