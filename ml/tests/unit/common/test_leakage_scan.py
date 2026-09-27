"""The leakage guard over every feature pipeline: declared source columns and the feature modules' source text
never name a post-outcome column (session 10b extends the list for the risk estimator)."""

from pathlib import Path

import pytest

import bank_agent.adapters.models.resolver_features as resolver_features
import bank_agent.adapters.models.text_features as text_features
import bank_ml.resolver.dataset as resolver_dataset
import bank_ml.resolver.gold as resolver_gold
import bank_ml.resolver.models as resolver_models
import bank_ml.router.models as router_models
from bank_ml.common.leakage import POST_OUTCOME_COLUMNS, assert_no_leakage, leaking, referenced_identifiers
from bank_ml.router import transcripts

FEATURE_MODULES = (text_features, resolver_features, router_models, resolver_models, resolver_dataset, resolver_gold)


@pytest.mark.parametrize(
    ("pipeline", "columns"),
    [
        ("resolver gold reader", resolver_gold.SOURCE_COLUMNS),
        ("router transcript analysis", transcripts.SOURCE_COLUMNS),
        ("resolver features", resolver_features.FEATURE_NAMES),
    ],
)
def test_declared_columns_pass_the_guard(pipeline: str, columns: tuple[str, ...]) -> None:
    assert_no_leakage(pipeline, columns)


@pytest.mark.parametrize("module", FEATURE_MODULES, ids=lambda module: module.__name__)
def test_feature_modules_never_quote_a_post_outcome_column(module: object) -> None:
    source = Path(str(getattr(module, "__file__", ""))).read_text(encoding="utf-8")
    assert leaking(referenced_identifiers(source)) == []


def test_the_guard_catches_a_quoted_outcome_column() -> None:
    assert leaking(referenced_identifiers('SQL = "select outcome_resolution, claimed_amount from complaints"')) == [
        "outcome_resolution"
    ]
    assert "affected_product_id" not in resolver_gold.SOURCE_COLUMNS
    assert {"status", "was_resolved", "sla_breached"} <= POST_OUTCOME_COLUMNS
