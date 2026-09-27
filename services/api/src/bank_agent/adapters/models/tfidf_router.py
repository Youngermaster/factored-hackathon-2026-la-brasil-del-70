"""``router:tfidf``: TF-IDF features with a multinomial logistic regression, evaluated in pure Python.

``bank-ml router train`` fits the model with scikit-learn over ``text_features.router_terms`` and exports plain
parameters (vocabulary, idf, term-major weights, intercepts, the dev-fitted temperature, and the dev-chosen
threshold) as a JSON artifact. This adapter loads it through ``ModelRegistry`` (digest checked) and never imports
scikit-learn, so the API image stays free of ML libraries and nothing is unpickled.
"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from bank_agent.adapters.models.registry import read_verified
from bank_agent.adapters.models.text_features import ANALYZER_ID, softmax, tfidf_vector
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import ModelArtifactIntegrityError
from bank_agent.domain.intelligence import IntentPrediction, IntentScore, ModelRef, ResolvedArtifact
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Intent

MAX_CANDIDATES = 5
Temperature = Annotated[float, Field(gt=0.0, le=100.0, allow_inf_nan=False)]
Threshold = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]


class LinearHead(BaseModel):
    """Classes, intercepts, temperature, and threshold shared by the linear routers' artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    classes: Annotated[tuple[Intent, ...], Field(min_length=2)]
    intercept: tuple[float, ...]
    temperature: Temperature = 1.0
    threshold: Threshold

    def predict(self, logits: list[float], model: ModelRef) -> IntentPrediction:
        probabilities = softmax(logits, self.temperature)
        order = sorted(range(len(self.classes)), key=lambda i: (-probabilities[i], self.classes[i].value))
        best = order[0]
        return IntentPrediction(
            intent=self.classes[best],
            confidence=min(1.0, max(0.0, probabilities[best])),
            candidates=tuple(
                IntentScore(intent=self.classes[i], score=min(1.0, max(0.0, probabilities[i])))
                for i in order[:MAX_CANDIDATES]
            ),
            below_threshold=probabilities[best] < self.threshold,
            model=model,
        )


class TfidfRouterArtifact(LinearHead):
    format: Literal["tfidf_logreg/1"]
    analyzer: Literal["router_terms@1"]
    vocabulary: tuple[str, ...]
    idf: tuple[float, ...]
    weights: tuple[tuple[float, ...], ...]
    """Term-major: ``weights[term][class]``."""

    @model_validator(mode="after")
    def _shapes(self) -> Self:
        if len(self.intercept) != len(self.classes) or len(set(self.classes)) != len(self.classes):
            raise ValueError("one intercept per distinct class")
        if not (len(self.vocabulary) == len(self.idf) == len(self.weights)):
            raise ValueError("vocabulary, idf, and weights must have one entry per term")
        if any(len(row) != len(self.classes) for row in self.weights):
            raise ValueError("every weight row needs one value per class")
        return self


class TfidfIntentRouter:
    """Implements ``IntentRouter`` from a ``tfidf_logreg/1`` artifact."""

    def __init__(self, artifact: TfidfRouterArtifact, model: ModelRef) -> None:
        if artifact.analyzer != ANALYZER_ID:
            raise ModelArtifactIntegrityError(f"artifact analyzer {artifact.analyzer} is not {ANALYZER_ID}")
        self._artifact = artifact
        self._index = {term: position for position, term in enumerate(artifact.vocabulary)}
        self.model = model

    @classmethod
    def load(cls, resolved: ResolvedArtifact) -> "TfidfIntentRouter":
        try:
            artifact = TfidfRouterArtifact.model_validate(read_verified(resolved))
        except ValueError as error:
            raise ModelArtifactIntegrityError(f"artifact {resolved.ref} is not a valid TF-IDF router") from error
        return cls(artifact, resolved.ref)

    @property
    def threshold(self) -> float:
        return self._artifact.threshold

    def logits(self, text: str) -> list[float]:
        artifact = self._artifact
        values = list(artifact.intercept)
        for position, weight in tfidf_vector(text, self._index, artifact.idf).items():
            row = artifact.weights[position]
            for klass in range(len(values)):
                values[klass] += weight * row[klass]
        return values

    def route(self, text: UntrustedText, language: Language) -> IntentPrediction:
        return self._artifact.predict(self.logits(text), self.model)
