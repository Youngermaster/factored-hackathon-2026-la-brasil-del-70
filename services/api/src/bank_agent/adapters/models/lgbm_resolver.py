"""``resolver:lgbm``: a LightGBM lambdarank model over the shared candidate features, evaluated in pure Python.

Ranking: candidates that pass the evidence gate (``resolver_features.plausible``) are scored by the tree ensemble
and ordered by score, then the most recent, then the id (the rules baseline's tie order). Scores become softmax
probabilities over the candidates plus a "none of these" option with the artifact's ``null_score``, so a lone or
weakly matching candidate does not look certain. ``clear_winner`` is set when the top probability beats both the
runner-up and the none option by the artifact's ``margin``. ``bank-ml`` chooses ``null_score`` and ``margin`` on the
dev split. A descriptor
with no clue at all yields an empty ranking, so the workflow asks for more detail. The resolver never fetches data.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from bank_agent.adapters.models.registry import read_verified
from bank_agent.adapters.models.resolver_features import (
    FEATURE_NAMES,
    FEATURES_ID,
    candidate_features,
    has_evidence,
    plausible,
)
from bank_agent.adapters.models.text_features import softmax
from bank_agent.adapters.models.tree_ensemble import TreeNode
from bank_agent.domain.errors import ModelArtifactIntegrityError
from bank_agent.domain.identifiers import TransactionId
from bank_agent.domain.intelligence import (
    ModelRef,
    RankedCandidate,
    ResolvedArtifact,
    TransactionDescriptor,
    TransactionResolution,
)
from bank_agent.domain.transaction import Transaction


class LgbmResolverArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format: Literal["lgbm_ranker/1"]
    features: Literal["resolver_features@1"]
    feature_names: tuple[str, ...]
    trees: Annotated[tuple[TreeNode, ...], Field(min_length=1)]
    margin: Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
    null_score: Annotated[float, Field(allow_inf_nan=False)]

    @model_validator(mode="after")
    def _features(self) -> Self:
        if self.feature_names != FEATURE_NAMES:
            raise ValueError("the artifact's feature list is not the shared feature list")
        if any(tree.max_feature() >= len(FEATURE_NAMES) for tree in self.trees):
            raise ValueError("a split names a feature outside the feature list")
        return self


class LgbmTransactionResolver:
    """Implements ``TransactionResolver`` from an ``lgbm_ranker/1`` artifact."""

    def __init__(self, artifact: LgbmResolverArtifact, model: ModelRef) -> None:
        if artifact.features != FEATURES_ID:
            raise ModelArtifactIntegrityError(f"artifact features {artifact.features} are not {FEATURES_ID}")
        self._artifact = artifact
        self.model = model

    @classmethod
    def load(cls, resolved: ResolvedArtifact) -> "LgbmTransactionResolver":
        try:
            artifact = LgbmResolverArtifact.model_validate(read_verified(resolved))
        except ValueError as error:
            raise ModelArtifactIntegrityError(f"artifact {resolved.ref} is not a valid LightGBM ranker") from error
        return cls(artifact, resolved.ref)

    @property
    def margin(self) -> float:
        return self._artifact.margin

    @property
    def null_score(self) -> float:
        return self._artifact.null_score

    def score_rows(self, rows: Sequence[Sequence[float]]) -> list[float]:
        return [sum(tree.evaluate(row) for tree in self._artifact.trees) for row in rows]

    def rank(
        self, descriptor: TransactionDescriptor, candidates: Sequence[Transaction], *, now: datetime
    ) -> TransactionResolution:
        unique = list({txn.transaction_id: txn for txn in candidates}.values())
        if not unique or not has_evidence(descriptor):
            return TransactionResolution(ranked=(), model=self.model)
        rows = candidate_features(descriptor, unique, now)
        kept = [(txn, row) for txn, row in zip(unique, rows, strict=True) if plausible(row)]
        if not kept:
            return TransactionResolution(ranked=(), model=self.model)
        scores = self.score_rows([row for _, row in kept])
        with_none = softmax([*scores, self._artifact.null_score])
        probabilities, none = with_none[:-1], with_none[-1]
        order = sorted(
            range(len(kept)),
            key=lambda i: (-scores[i], -kept[i][0].occurred_at.timestamp(), kept[i][0].transaction_id),
        )
        ranked = tuple(
            RankedCandidate(transaction_id=kept[i][0].transaction_id, score=round(probabilities[i], 6), rank=rank)
            for rank, i in enumerate(order, start=1)
        )
        runner_up = max(ranked[1].score if len(ranked) > 1 else 0.0, none)
        margin = round(ranked[0].score - runner_up, 6)
        winner: TransactionId | None = ranked[0].transaction_id if margin >= self._artifact.margin else None
        return TransactionResolution(ranked=ranked, margin=margin, clear_winner=winner, model=self.model)
