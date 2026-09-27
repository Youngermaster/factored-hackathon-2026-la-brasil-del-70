"""Resolver features, the evidence gate, the tree evaluator, and ``resolver:lgbm`` on a hand-written artifact."""

import math
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from bank_agent.adapters.models.lgbm_resolver import LgbmTransactionResolver
from bank_agent.adapters.models.resolver_features import (
    FEATURE_NAMES,
    UNKNOWN,
    candidate_features,
    category_hint,
    has_evidence,
    merchant_similarity,
    plausible,
)
from bank_agent.adapters.models.tree_ensemble import TreeEnsemble, TreeNode
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import ModelArtifactIntegrityError
from bank_agent.domain.intelligence import DateRange, TransactionDescriptor
from bank_agent.domain.transaction import TransactionCategory, TransactionChannel
from bank_agent_builders import T0, transaction
from bank_agent_models import LGBM_ARTIFACT, publish

NOW = T0.astimezone(ZoneInfo("America/Mexico_City"))


def described(**fields: object) -> TransactionDescriptor:
    return TransactionDescriptor.model_validate(fields)


def row_of(descriptor: TransactionDescriptor, *txns: object) -> dict[str, float]:
    rows = candidate_features(descriptor, list(txns), NOW)  # type: ignore[arg-type]
    return dict(zip(FEATURE_NAMES, rows[0], strict=True))


def test_missing_clues_are_encoded_as_unknown_never_nan() -> None:
    row = row_of(described(), transaction())
    assert (row["amount_given"], row["amount_rel_diff"]) == (0.0, UNKNOWN)
    assert (row["date_distance_days"], row["merchant_similarity"]) == (UNKNOWN, UNKNOWN)
    assert (row["channel_match"], row["category_match"]) == (UNKNOWN, UNKNOWN)
    assert not any(math.isnan(value) for value in row.values())
    assert has_evidence(described()) is False


def test_amount_date_merchant_and_context_features() -> None:
    near = transaction("T1", amount="1000.00", occurred_at=T0 - timedelta(days=3), merchant_name="Super Ahorro")
    far = transaction("T2", amount="5000.00", occurred_at=T0 - timedelta(days=3), merchant_name="Uber")
    day = (T0 - timedelta(days=3)).astimezone(NOW.tzinfo).date()
    descriptor = described(
        amount=Decimal("1010"),
        currency_hint="MXN",
        merchant_text=UntrustedText("super ahoro"),
        date_interpretations=[DateRange(start=day, end=day)],
        channel_hint=TransactionChannel.POS,
    )
    rows = candidate_features(descriptor, [near, far], NOW)
    first = dict(zip(FEATURE_NAMES, rows[0], strict=True))
    second = dict(zip(FEATURE_NAMES, rows[1], strict=True))
    assert first["amount_rel_diff"] == pytest.approx(0.01)
    assert first["amount_log_abs_diff"] == pytest.approx(math.log1p(10))
    assert (first["currency_match"], first["amount_closeness_rank"], second["amount_closeness_rank"]) == (1.0, 0.0, 1.0)
    assert (first["date_given"], first["date_distance_days"], first["date_ambiguous"]) == (1.0, 0.0, 0.0)
    assert first["merchant_similarity"] > 0.9 > second["merchant_similarity"]
    assert first["category_match"] == 1.0
    assert first["channel_match"] == 1.0
    assert (first["same_day_count"], first["candidate_count"], first["recency_rank"]) == (2.0, 2.0, 0.0)
    assert plausible(rows[0]) is True


def test_category_hints_and_the_gate() -> None:
    assert category_hint(described(merchant_text=UntrustedText("el uber de anoche"))) is TransactionCategory.TRANSPORT
    assert category_hint(described(merchant_text=UntrustedText("zzz"))) is None
    assert merchant_similarity(described(merchant_text=UntrustedText("uber")), transaction(merchant_name=None)) == 0.0
    unrelated = candidate_features(described(amount=Decimal("99999")), [transaction(amount="10.00")], NOW)[0]
    assert plausible(unrelated) is False


def test_ambiguous_dates_use_the_nearest_interpretation() -> None:
    day = (T0 - timedelta(days=3)).astimezone(NOW.tzinfo).date()
    ranges = [DateRange(start=day - timedelta(days=30), end=day - timedelta(days=30)), DateRange(start=day, end=day)]
    row = row_of(described(date_interpretations=ranges), transaction())
    assert (row["date_distance_days"], row["date_ambiguous"]) == (0.0, 1.0)


def test_tree_nodes_follow_lightgbm_missing_value_rules() -> None:
    def split(missing: str, default_left: bool) -> TreeNode:
        return TreeNode.model_validate(
            {
                "feature": 0,
                "threshold": 0.5,
                "default_left": default_left,
                "missing": missing,
                "left": {"value": 1.0},
                "right": {"value": 2.0},
            }
        )

    assert split("none", False).evaluate([0.4]) == 1.0
    assert split("none", False).evaluate([math.nan]) == 1.0
    assert split("nan", False).evaluate([math.nan]) == 2.0
    assert split("zero", False).evaluate([0.0]) == 2.0
    assert split("zero", True).evaluate([0.9]) == 2.0
    ensemble = TreeEnsemble(trees=(split("none", True), TreeNode(value=0.5)), feature_count=1)
    assert ensemble.score([0.9]) == 2.5
    with pytest.raises(ValueError, match="expected 1 features"):
        ensemble.score([1.0, 2.0])
    with pytest.raises(ValueError, match="outside the feature list"):
        TreeEnsemble(trees=(split("none", True),), feature_count=0)
    with pytest.raises(ValueError, match="leaf has only a value"):
        TreeNode(value=1.0, feature=0)
    with pytest.raises(ValueError, match="split needs"):
        TreeNode(feature=0, threshold=1.0)


def test_lgbm_resolver_ranks_plausible_candidates_with_a_margin(tmp_path: Path) -> None:
    resolver = LgbmTransactionResolver.load(publish(tmp_path, "resolver:lgbm", LGBM_ARTIFACT))
    exact = transaction("T1", amount="1000.00", merchant_name="Super Ahorro")
    other = transaction("T2", amount="1003.00", merchant_name="Uber", occurred_at=T0 - timedelta(days=1))
    unrelated = transaction("T3", amount="50.00", merchant_name="Cine Premium")
    resolution = resolver.rank(
        described(amount=Decimal("1000"), merchant_text=UntrustedText("ahoro")),
        [exact, other, unrelated, exact],
        now=NOW,
    )
    assert [candidate.transaction_id for candidate in resolution.ranked] == ["T1", "T2"]
    assert resolution.clear_winner == "T1"
    assert resolution.margin is not None
    assert resolution.margin >= resolver.margin
    assert sum(candidate.score for candidate in resolution.ranked) == pytest.approx(1.0, abs=1e-5)


def test_lgbm_resolver_returns_nothing_without_evidence_or_plausible_candidates(tmp_path: Path) -> None:
    resolver = LgbmTransactionResolver.load(publish(tmp_path, "resolver:lgbm", LGBM_ARTIFACT))
    assert resolver.rank(described(), [transaction()], now=NOW).ranked == ()
    assert resolver.rank(described(amount=Decimal("1")), [], now=NOW).ranked == ()
    assert resolver.rank(described(amount=Decimal("99999")), [transaction(amount="5.00")], now=NOW).ranked == ()


def test_lgbm_resolver_ties_go_to_the_most_recent(tmp_path: Path) -> None:
    resolver = LgbmTransactionResolver.load(publish(tmp_path, "resolver:lgbm", LGBM_ARTIFACT))
    older = transaction("T1", amount="100.00", occurred_at=T0 - timedelta(days=5), merchant_name=None)
    newer = transaction("T2", amount="100.00", occurred_at=T0 - timedelta(days=2), merchant_name=None)
    resolution = resolver.rank(described(amount=Decimal("100")), [older, newer], now=NOW)
    assert [candidate.transaction_id for candidate in resolution.ranked] == ["T2", "T1"]
    assert resolution.clear_winner is None


@pytest.mark.parametrize("change", [{"feature_names": ["x"]}, {"trees": []}, {"margin": 2.0}])
def test_malformed_lgbm_artifacts_are_refused(tmp_path: Path, change: dict[str, object]) -> None:
    with pytest.raises(ModelArtifactIntegrityError):
        LgbmTransactionResolver.load(publish(tmp_path, "resolver:lgbm", {**LGBM_ARTIFACT, **change}))
