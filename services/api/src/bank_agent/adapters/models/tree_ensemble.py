"""A pure-Python evaluator for gradient-boosted trees exported from LightGBM.

``bank-ml`` converts LightGBM's ``dump_model()`` into the compact node format below; only numerical ``<=`` splits
are supported (the resolver has no categorical features), and an export with anything else is refused at training
time and again here. The prediction is the sum of the leaf values, which equals LightGBM's raw score; an
integration test in ``ml/tests`` checks the equality on a trained model.

Missing values follow LightGBM: with ``missing = "nan"`` a NaN goes to the default side; with ``"zero"`` a zero or NaN
does; with ``"none"`` a NaN is treated as zero.
"""

import math
from collections.abc import Sequence
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

ZERO_THRESHOLD = 1e-35


class TreeNode(BaseModel):
    """A split (``feature``, ``threshold``, ``left``, ``right``) or a leaf (``value`` only)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature: int | None = None
    threshold: float | None = None
    default_left: bool = True
    missing: Literal["none", "zero", "nan"] = "none"
    left: "TreeNode | None" = None
    right: "TreeNode | None" = None
    value: float | None = None

    @model_validator(mode="after")
    def _shape(self) -> Self:
        split = (self.feature, self.threshold, self.left, self.right)
        if self.value is not None:
            if any(part is not None for part in split):
                raise ValueError("a leaf has only a value")
        elif any(part is None for part in split) or (self.feature is not None and self.feature < 0):
            raise ValueError("a split needs a non-negative feature, a threshold, and two children")
        return self

    def evaluate(self, row: Sequence[float]) -> float:
        node = self
        while node.value is None:
            if node.feature is None or node.threshold is None or node.left is None or node.right is None:
                raise ValueError("malformed split node")
            value = row[node.feature]
            if math.isnan(value) and node.missing == "none":
                value = 0.0
            is_missing = (node.missing == "nan" and math.isnan(value)) or (
                node.missing == "zero" and (math.isnan(value) or abs(value) <= ZERO_THRESHOLD)
            )
            go_left = node.default_left if is_missing else value <= node.threshold
            node = node.left if go_left else node.right
        return node.value

    def max_feature(self) -> int:
        if self.value is not None or self.left is None or self.right is None or self.feature is None:
            return -1
        return max(self.feature, self.left.max_feature(), self.right.max_feature())


class TreeEnsemble(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trees: tuple[TreeNode, ...]
    feature_count: int

    @model_validator(mode="after")
    def _features(self) -> Self:
        if any(tree.max_feature() >= self.feature_count for tree in self.trees):
            raise ValueError("a split names a feature outside the feature list")
        return self

    def score(self, row: Sequence[float]) -> float:
        if len(row) != self.feature_count:
            raise ValueError(f"expected {self.feature_count} features, got {len(row)}")
        return sum(tree.evaluate(row) for tree in self.trees)
