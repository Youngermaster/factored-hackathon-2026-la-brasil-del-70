"""The pre-registered scoring: criterion normalization, weighted scores, ordering with ties, weight
sensitivity, and sub-intent classes (``docs/analysis/workflow-scoring-preregistration.md``)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from bank_data.analysis.config import CRITERIA

SubIntentClass = Literal["automate", "clarify_first", "hand_off"]


def ratio_to_max(values: Mapping[str, float]) -> dict[str, float]:
    """Each value over the largest one (all zero when the largest is not positive)."""
    top = max(values.values(), default=0.0)
    if top <= 0:
        return dict.fromkeys(values, 0.0)
    return {key: value / top for key, value in values.items()}


def harm_inverse(harm: int) -> float:
    """``(5 - harm) / 4`` for a harm rating from 1 (low) to 5 (high)."""
    if not 1 <= harm <= 5:
        raise ValueError("harm must be between 1 and 5")
    return (5 - harm) / 4


def weighted_score(criteria: Mapping[str, float], weights: Mapping[str, float]) -> float:
    """Sum of weight times criterion value over the sum of weights, times 100."""
    if set(criteria) != set(CRITERIA) or set(weights) != set(CRITERIA):
        raise ValueError(f"criteria and weights must name exactly {', '.join(CRITERIA)}")
    for name, value in criteria.items():
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"criterion {name} must lie between 0 and 1, got {value}")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("weights must have a positive sum")
    return 100.0 * sum(weights[name] * criteria[name] for name in CRITERIA) / total


def perturbed_weights(weights: Mapping[str, float], criterion: str, delta: float) -> dict[str, float]:
    """Move one weight by ``delta`` points (floored at zero), then renormalize all weights to sum to 100."""
    if criterion not in weights:
        raise KeyError(criterion)
    moved = dict(weights)
    moved[criterion] = max(0.0, moved[criterion] + delta)
    total = sum(moved.values())
    if total <= 0:
        raise ValueError("perturbed weights have no positive sum")
    return {name: 100.0 * value / total for name, value in moved.items()}


@dataclass(frozen=True)
class Candidate:
    name: str
    score: float
    data_support: float
    harm: int


def order(candidates: list[Candidate], *, tie_margin: float) -> list[str]:
    """Descending score; adjacent scores closer than ``tie_margin`` are a tie, broken by higher data
    support and then lower harm (and finally the name, for determinism)."""
    ranked = sorted(candidates, key=lambda item: (-item.score, item.name))
    changed = True
    while changed:
        changed = False
        for index in range(len(ranked) - 1):
            first, second = ranked[index], ranked[index + 1]
            if abs(first.score - second.score) < tie_margin and _tiebreak(second) < _tiebreak(first):
                ranked[index], ranked[index + 1] = second, first
                changed = True
    return [item.name for item in ranked]


def _tiebreak(item: Candidate) -> tuple[float, int, str]:
    return (-item.data_support, item.harm, item.name)


@dataclass(frozen=True)
class Variant:
    label: str
    weights: dict[str, float]
    scores: dict[str, float]
    ranking: list[str]


def weight_sensitivity(
    criteria: Mapping[str, Mapping[str, float]],
    weights: Mapping[str, float],
    *,
    delta: float,
    harm: Mapping[str, int],
    tie_margin: float,
) -> list[Variant]:
    """The ranking under every single-weight move of plus and minus ``delta`` points (renormalized)."""
    variants: list[Variant] = []
    for criterion in CRITERIA:
        for signed in (delta, -delta):
            moved = perturbed_weights(weights, criterion, signed)
            scores = {name: weighted_score(values, moved) for name, values in criteria.items()}
            ranking = order(
                [Candidate(name, scores[name], criteria[name]["data_support"], harm[name]) for name in criteria],
                tie_margin=tie_margin,
            )
            label = f"{criterion} {'+' if signed > 0 else '-'}{delta:g}"
            variants.append(Variant(label, moved, scores, ranking))
    return variants


def classify_sub_intent(capability: float, data_support: float, *, threshold: float) -> SubIntentClass:
    """Hand off at capability 0; clarify first when the records support the sub-intent poorly; else automate."""
    if capability <= 0:
        return "hand_off"
    if data_support < threshold:
        return "clarify_first"
    return "automate"
