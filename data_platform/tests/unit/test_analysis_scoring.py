import pytest

from bank_data.analysis.config import CRITERIA
from bank_data.analysis.scoring import (
    Candidate,
    classify_sub_intent,
    harm_inverse,
    order,
    perturbed_weights,
    ratio_to_max,
    weight_sensitivity,
    weighted_score,
)

WEIGHTS = {
    "demand": 20.0,
    "pain": 25.0,
    "automatable_share": 20.0,
    "harm_inverse": 10.0,
    "data_support": 15.0,
    "demo_depth": 10.0,
}


def _criteria(value: float) -> dict[str, float]:
    return dict.fromkeys(CRITERIA, value)


def test_ratio_to_max_scales_by_the_largest_value() -> None:
    assert ratio_to_max({"a": 2.0, "b": 1.0, "c": 0.0}) == {"a": 1.0, "b": 0.5, "c": 0.0}
    assert ratio_to_max({"a": 0.0, "b": 0.0}) == {"a": 0.0, "b": 0.0}


def test_harm_inverse_maps_one_to_one_and_five_to_zero() -> None:
    assert harm_inverse(1) == 1.0
    assert harm_inverse(3) == 0.5
    assert harm_inverse(5) == 0.0
    with pytest.raises(ValueError, match="between 1 and 5"):
        harm_inverse(6)


def test_weighted_score_matches_a_hand_computed_example() -> None:
    criteria = {
        "demand": 1.0,
        "pain": 0.4,
        "automatable_share": 0.5,
        "harm_inverse": 0.75,
        "data_support": 0.8,
        "demo_depth": 0.6,
    }
    # 20 + 10 + 10 + 7.5 + 12 + 6 = 65.5 out of 100.
    assert weighted_score(criteria, WEIGHTS) == pytest.approx(65.5)
    assert weighted_score(_criteria(1.0), WEIGHTS) == pytest.approx(100.0)


def test_weighted_score_rejects_out_of_range_or_missing_criteria() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        weighted_score({**_criteria(0.5), "pain": 1.5}, WEIGHTS)
    with pytest.raises(ValueError, match="exactly"):
        weighted_score({"demand": 1.0}, WEIGHTS)
    with pytest.raises(ValueError, match="positive sum"):
        weighted_score(_criteria(0.5), dict.fromkeys(CRITERIA, 0.0))


def test_perturbed_weights_renormalize_to_one_hundred() -> None:
    moved = perturbed_weights(WEIGHTS, "pain", 5)
    assert sum(moved.values()) == pytest.approx(100.0)
    assert moved["pain"] == pytest.approx(30 / 105 * 100)
    assert moved["demand"] == pytest.approx(20 / 105 * 100)
    lowered = perturbed_weights({**WEIGHTS, "demo_depth": 3.0}, "demo_depth", -5)
    assert lowered["demo_depth"] == 0.0
    assert sum(lowered.values()) == pytest.approx(100.0)
    with pytest.raises(KeyError):
        perturbed_weights(WEIGHTS, "unknown", 5)


def test_order_breaks_ties_by_data_support_then_harm() -> None:
    candidates = [
        Candidate("a", 70.0, data_support=0.3, harm=2),
        Candidate("b", 69.0, data_support=0.9, harm=3),
        Candidate("c", 60.0, data_support=0.9, harm=1),
        Candidate("d", 59.5, data_support=0.9, harm=4),
    ]
    # a and b are within the 2-point margin: b has more data support. c and d tie on data support: c has less harm.
    assert order(candidates, tie_margin=2.0) == ["b", "a", "c", "d"]
    assert order(candidates, tie_margin=0.0) == ["a", "b", "c", "d"]


def test_weight_sensitivity_yields_twelve_renormalized_variants() -> None:
    criteria = {
        "x": {**_criteria(0.5), "demand": 1.0},
        "y": {**_criteria(0.5), "pain": 1.0},
    }
    variants = weight_sensitivity(criteria, WEIGHTS, delta=5, harm={"x": 2, "y": 2}, tie_margin=0.0)
    assert len(variants) == 12
    assert all(sum(variant.weights.values()) == pytest.approx(100.0) for variant in variants)
    by_label = {variant.label: variant for variant in variants}
    # Base weights: x scores 60.0 and y 62.5. Lowering pain to 20 (of 95) puts x first: 60/95 against 57.5/95.
    assert by_label["pain +5"].ranking == ["y", "x"]
    assert by_label["pain -5"].ranking == ["x", "y"]


def test_sub_intent_classes_follow_capability_and_data_support() -> None:
    assert classify_sub_intent(0.0, 1.0, threshold=0.5) == "hand_off"
    assert classify_sub_intent(0.5, 0.4, threshold=0.5) == "clarify_first"
    assert classify_sub_intent(1.0, 0.5, threshold=0.5) == "automate"
