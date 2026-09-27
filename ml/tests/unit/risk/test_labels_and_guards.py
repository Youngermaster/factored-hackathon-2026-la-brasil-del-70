"""The risk label with one and with two snapshots, the protected-attribute and leakage guards, and the splits."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import bank_agent.adapters.models.learned_risk as learned_risk
import bank_agent.adapters.models.risk_artifact as risk_artifact
import bank_agent.adapters.models.risk_features as risk_features
import bank_ml.risk.calibration as risk_calibration
import bank_ml.risk.models as risk_models
import bank_ml.risk.scoring as risk_scoring
import bank_ml.risk.training as risk_training
import bank_ml.risk.uncertainty as risk_uncertainty
from bank_ml.common.leakage import (
    PROTECTED_COLUMNS,
    RISK_DENYLIST,
    LeakageError,
    assert_risk_features_clean,
    leaking,
    referenced_names,
)
from bank_ml.risk.dataset import income_band, income_cuts, part_of
from bank_ml.risk.gold import FEATURE_COLUMNS, LABEL_COLUMNS, SLICE_COLUMNS
from bank_ml.risk.labels import LABEL_DEFINITION, LabelConfig, Outcome, build_labels, label_of

T = date(2026, 6, 17)
FEATURE_MODULES = (
    risk_features,
    risk_artifact,
    learned_risk,
    risk_models,
    risk_scoring,
    risk_calibration,
    risk_training,
    risk_uncertainty,
)


@pytest.mark.parametrize(
    ("outcome", "label"),
    [
        (Outcome(T, 0, 0), 0),
        (Outcome(T, 15, 0), 0),
        (Outcome(T, 30, 0), 1),
        (Outcome(T, 180, 0), 1),
        (Outcome(T, 60, 1), None),
        (Outcome(T, None, 2), None),
    ],
)
def test_the_label_is_thirty_days_past_due_on_any_open_credit_product(outcome: Outcome, label: int | None) -> None:
    assert label_of(outcome) == label


def test_one_snapshot_gives_a_cross_sectional_label_and_counts_exclusions() -> None:
    outcomes = {"a": Outcome(T, 30, 0), "b": Outcome(T, 0, 0), "c": Outcome(T, None, 1), "d": Outcome(T, 0, 1)}
    labels, counts = build_labels(LabelConfig(T), outcomes)
    assert labels == {"a": 1, "b": 0}
    assert (counts.labeled, counts.positives, counts.unknown, counts.partly_unknown) == (2, 1, 1, 1)
    assert not LabelConfig(T).forward_looking
    assert LABEL_DEFINITION == "snapshot_dpd30_any_credit_product"


def test_two_snapshots_give_a_forward_label_strictly_after_the_features() -> None:
    config = LabelConfig(T, horizon_days=30)
    later = date(2026, 7, 17)
    assert config.forward_looking
    assert config.outcome_snapshot == later
    labels, _ = build_labels(config, {"a": Outcome(later, 60, 0)})
    assert labels == {"a": 1}
    with pytest.raises(ValueError, match="forward-looking"):
        build_labels(config, {"a": Outcome(T, 60, 0)})
    with pytest.raises(ValueError, match="cross-sectional"):
        build_labels(LabelConfig(T), {"a": Outcome(later, 60, 0)})
    with pytest.raises(ValueError, match="negative"):
        LabelConfig(T, horizon_days=-1)


def test_feature_columns_pass_the_risk_guard_and_label_columns_would_not() -> None:
    assert_risk_features_clean("risk features", FEATURE_COLUMNS)
    assert_risk_features_clean("shared features", risk_features.FEATURE_NAMES)
    assert leaking(LABEL_COLUMNS, RISK_DENYLIST) == ["customer_id", "product_status", "days_past_due"]
    assert set(leaking(SLICE_COLUMNS, RISK_DENYLIST)) == {"customer_id", "segment"}
    assert "max_days_past_due" not in FEATURE_COLUMNS


@pytest.mark.parametrize(
    "column",
    [
        "days_past_due",
        "max_days_past_due",
        "days_past_due_at_snapshot",
        "worst_days_past_due_bucket",
        "customer_status",
        "gender",
        "date_of_birth",
        "age",
        "marital_status",
        "detected_accent",
        "city",
        "state",
        "postal_code",
        "segment",
        "occupation",
        "education_level",
        "document_number",
        "customer_id",
        "resolution",
    ],
)
def test_the_risk_guard_refuses_protected_label_and_identifier_columns(column: str) -> None:
    with pytest.raises(LeakageError, match=column):
        assert_risk_features_clean("risk features", ("credit_score", column))


@pytest.mark.parametrize("module", FEATURE_MODULES, ids=lambda module: module.__name__)
def test_feature_modules_never_name_a_denied_column(module: object) -> None:
    source = Path(str(getattr(module, "__file__", ""))).read_text(encoding="utf-8")
    names = referenced_names(source)
    assert sorted(names & RISK_DENYLIST) == []
    assert not [name for name in names if "days_past_due" in name]


def test_the_name_scan_sees_attributes_and_keywords() -> None:
    source = "def f(profile):\n    return g(profile.max_days_past_due, segment=1)\n"
    assert {"max_days_past_due", "segment"} <= referenced_names(source)
    assert {"gender", "segment", "detected_accent", "postal_code"} <= PROTECTED_COLUMNS


def test_dev_halves_are_deterministic_and_only_split_dev() -> None:
    assert part_of("CLI-1", "train") == "train"
    assert part_of("CLI-1", "test") == "test"
    halves = {part_of(f"CLI-{i}", "dev") for i in range(200)}
    assert halves == {"calibration", "selection"}
    assert all(part_of(f"CLI-{i}", "dev") == part_of(f"CLI-{i}", "dev") for i in range(50))


def test_income_bands_are_within_country_tertiles_from_train() -> None:
    cuts = income_cuts([("MX", Decimal(v)) for v in (1, 2, 3, 4, 5, 6)] + [("AR", None)])
    assert set(cuts) == {"MX"}
    assert income_band("MX", Decimal("1"), cuts) == "lower"
    assert income_band("MX", Decimal("3.5"), cuts) == "middle"
    assert income_band("MX", Decimal("6"), cuts) == "upper"
    assert income_band("MX", None, cuts) == "missing"
    assert income_band("AR", Decimal("5"), cuts) == "missing"
