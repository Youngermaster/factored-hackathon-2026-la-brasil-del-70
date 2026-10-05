"""Model inventory and model card invariants: what serves is consistent, metrics sit inside their intervals."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from bank_agent.domain.evaluation import MetricCount
from bank_agent.domain.intelligence import ModelComponent, ModelRef, PromptRef
from bank_agent.domain.model_inventory import (
    CardMetric,
    LlmConfiguration,
    LlmModelSetup,
    ModelCard,
    ModelCardSet,
    ModelInventory,
    PromotionDecision,
    PromotionRow,
    PromptUse,
    ServedModel,
)
from bank_agent.domain.workflow import WorkflowId

KEYWORD = ModelRef.model_validate("router:keyword@1")


def served(**values: Any) -> ServedModel:
    fields: dict[str, Any] = {"component": ModelComponent.ROUTER, "selected": "keyword@1", "served": KEYWORD,
                              "kind": "baseline"}  # fmt: skip
    return ServedModel.model_validate({**fields, **values})


def llm(**values: Any) -> LlmConfiguration:
    fields: dict[str, Any] = {
        "provider": "fake", "configured": False, "models": (), "fallback_enabled": False, "understanding": True,
        "phrasing": False, "handoff_summary": False, "daily_budget_usd": Decimal(5),
        "conversation_budget_usd": Decimal("0.50"), "session_token_limit": 20000,
        "unverified_price_multiplier": Decimal("1.5"),
    }  # fmt: skip
    return LlmConfiguration.model_validate({**fields, **values})


def card(**values: Any) -> ModelCard:
    fields: dict[str, Any] = {
        "component": "router", "model": "router:keyword@1", "role": "default", "split": "test", "sample_size": 601,
        "sample_unit": "items", "kind": "provisional", "metrics": [{"name": "accuracy", "value": 0.381}],
        "source": "docs/models/router.md", "report": "docs/evaluation/router.md",
        "generated_at": "2026-09-27T20:09:44Z", "git_sha": "2c19633",
    }  # fmt: skip
    return ModelCard.model_validate({**fields, **values})


def row(served_row: bool, safe: int = 74) -> PromotionRow:
    return PromotionRow(
        models=("router:keyword@1",),
        served=served_row,
        cases=112,
        safe_automated_resolution=MetricCount(count=safe, denominator=112),
        unsafe_outcomes=MetricCount(count=0, denominator=112),
    )


def test_a_served_component_is_consistent_with_its_kind_and_fallback() -> None:
    assert served().kind == "baseline"
    with pytest.raises(ValidationError, match="names its reason"):
        served(fell_back=True)
    with pytest.raises(ValidationError, match="names its reason"):
        served(reason="artifact_not_found")
    with pytest.raises(ValidationError, match="unavailable exactly when"):
        served(served=None)
    with pytest.raises(ValidationError, match="belongs to the component"):
        served(served="resolver:rules@1")
    nothing = served(component="risk_estimator", selected="logreg@champion", served=None, kind="unavailable",
                     fell_back=True, reason="artifact_not_found")  # fmt: skip
    assert nothing.model_dump(mode="json")["served"] is None


def test_the_language_model_setup_names_its_models_when_configured() -> None:
    primary = LlmModelSetup(
        role="primary",
        model_id="azure/gpt-4.1-mini",
        price_basis="verified",
        input_usd_per_million=Decimal("0.40"),
        output_usd_per_million=Decimal("1.60"),
    )
    assert llm(configured=True, models=(primary,)).models[0].model_id == "azure/gpt-4.1-mini"
    with pytest.raises(ValidationError, match="names its primary"):
        llm(configured=True)
    with pytest.raises(ValidationError, match="names its primary"):
        llm(models=(primary,))
    with pytest.raises(ValidationError, match="enabled fallback"):
        llm(configured=True, models=(primary,), fallback_enabled=True)
    with pytest.raises(ValidationError, match="once"):
        llm(configured=True, models=(primary, primary))


def test_a_prompt_the_engine_never_calls_is_never_active() -> None:
    prompt = PromptRef.model_validate("classify_intent_fallback@1")
    with pytest.raises(ValidationError, match="never active"):
        PromptUse(prompt=prompt, purpose="not_called_by_engine", active=True)


def test_the_inventory_lists_each_component_and_prompt_once() -> None:
    prompt = PromptUse(prompt=PromptRef.model_validate("phrase_response@1"), purpose="phrasing", active=False)
    fields: dict[str, Any] = {"generated_at": datetime(2026, 10, 5, tzinfo=UTC), "llm": llm(),
                              "policy_pack_version": "pack-1", "workflows_enabled": (WorkflowId.CREDIT,)}  # fmt: skip
    assert ModelInventory(components=(served(),), prompts=(prompt,), **fields).components[0].served == KEYWORD
    with pytest.raises(ValidationError, match="component is listed once"):
        ModelInventory(components=(served(), served()), prompts=(), **fields)
    with pytest.raises(ValidationError, match="prompt version is listed once"):
        ModelInventory(components=(), prompts=(prompt, prompt), **fields)


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"value": 0.5, "low": 0.4}, "both bounds"),
        ({"value": 0.5, "low": 0.6, "high": 0.7}, "inside its interval"),
        ({"value": 1.2}, "between 0 and 1"),
        ({"value": -1.0, "unit": "ms"}, "not negative"),
    ],
)
def test_card_metrics_sit_inside_their_intervals(values: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        CardMetric.model_validate({"name": "accuracy", **values})
    assert CardMetric(name="latency_p95_ms", value=7.57, unit="ms").value == 7.57


def test_cards_cite_relative_paths_and_their_own_component() -> None:
    assert card().model == KEYWORD
    with pytest.raises(ValidationError, match="relative paths"):
        card(report="../outside.md")
    with pytest.raises(ValidationError, match="belongs to its component"):
        card(component="resolver")
    with pytest.raises(ValidationError, match="once per card"):
        card(metrics=[{"name": "accuracy", "value": 0.3}, {"name": "accuracy", "value": 0.4}])
    with pytest.raises(ValidationError, match="appears once"):
        ModelCardSet(cards=(card(), card()))


def test_a_promotion_decision_serves_exactly_one_configuration() -> None:
    fields: dict[str, Any] = {"decision": "router_defaults", "outcome": "keep_baselines",
                              "reason": "overlapping_intervals", "workflows": ("dispute",), "split": "dev",
                              "measurement": "simulated", "language_model": "ollama/qwen2.5:7b-instruct",
                              "session": "session_14b", "source": "docs/evaluation/results.md"}  # fmt: skip
    decision = PromotionDecision.model_validate({**fields, "rows": (row(True), row(False, 75))})
    assert [item.served for item in decision.rows] == [True, False]
    with pytest.raises(ValidationError, match="exactly one"):
        PromotionDecision.model_validate({**fields, "rows": (row(True), row(True))})
    with pytest.raises(ValidationError, match="over the row's cases"):
        PromotionRow(
            models=("router:keyword@1",),
            served=True,
            cases=10,
            safe_automated_resolution=MetricCount(count=1, denominator=112),
            unsafe_outcomes=MetricCount(count=0, denominator=10),
        )
