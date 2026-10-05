"""The model inventory the container records at startup: served models, language model setup, prompts, policy."""

import secrets
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from bank_agent.adapters.reliability.monitor import LlmHealth
from bank_agent.bootstrap.container import Container
from bank_agent.bootstrap.inventory import build_model_inventory
from bank_agent.bootstrap.llm import LlmOverrides
from bank_agent.bootstrap.settings import load_settings
from bank_agent.domain.intelligence import ModelComponent
from bank_agent.domain.workflow import WorkflowId
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.fake_llm import FakeLLM

STARTED = datetime(2026, 10, 5, 15, 30, tzinfo=UTC)
PRICES = """schema_version: 1
currency: USD
unverified_price_multiplier: "1.5"
models:
  - model_id: azure/gpt-4.1-mini
    input_usd_per_million: "0.40"
    output_usd_per_million: "1.60"
    effective_date: 2026-10-05
    source_url: https://prices.azure.com/api/retail/prices
    verified: true
  - model_id: other/model
    input_usd_per_million: "2.00"
    output_usd_per_million: "8.00"
    effective_date: 2026-10-05
    source_url: https://example.com/prices
    verified: false
"""


def test_a_default_process_serves_the_baselines_and_no_language_model() -> None:
    container = Container(load_settings(env_file=None), clock=FixedClock(STARTED))
    inventory = container.model_inventory
    assert [(item.component, str(item.served), item.kind) for item in inventory.components] == [
        (ModelComponent.ROUTER, "router:keyword@1", "baseline"),
        (ModelComponent.RESOLVER, "resolver:rules@1", "baseline"),
        (ModelComponent.RISK_ESTIMATOR, "risk_estimator:score_band@1", "baseline"),
        (ModelComponent.RETRIEVER, "retriever:bm25@1", "baseline"),
        (ModelComponent.LANGUAGE_DETECTOR, "language_detector:lexical@1", "baseline"),
    ]
    assert (inventory.llm.provider, inventory.llm.configured, inventory.llm.models) == ("fake", False, ())
    assert not any(use.active for use in inventory.prompts)
    assert inventory.generated_at == STARTED
    assert inventory.policy_pack_version == container.policy.pack.version
    assert inventory.workflows_enabled == tuple(WorkflowId)


def test_configured_models_carry_their_price_basis_and_no_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prices = tmp_path / "prices.yaml"
    prices.write_text(PRICES, encoding="utf-8")
    secret = secrets.token_urlsafe(32)
    base = "https://private-endpoint.example.internal/"
    for name, value in {
        "LLM_PRIMARY_MODEL": "azure/gpt-4.1-mini", "LLM_FALLBACK_MODEL": "azure/gpt-4o",
        "LLM_API_KEY_PRIMARY": secret, "LLM_API_KEY_FALLBACK": secret, "LLM_API_BASE": base,
        "LLM_PRICES_FILE": str(prices), "LLM_DAILY_BUDGET_USD": "10", "LLM_SESSION_TOKEN_LIMIT": "200000",
        "WORKFLOW_LLM_PHRASING": "true",
    }.items():  # fmt: skip
        monkeypatch.setenv(name, value)
    overrides = LlmOverrides(primary=FakeLLM(), fallback=FakeLLM())
    container = Container(load_settings(env_file=None), llm_overrides=overrides, clock=FixedClock(STARTED))
    llm = container.model_inventory.llm
    primary, fallback = llm.models
    assert (primary.role, primary.model_id, primary.price_basis) == ("primary", "azure/gpt-4.1-mini", "verified")
    assert (primary.input_usd_per_million, primary.output_usd_per_million) == (Decimal("0.40"), Decimal("1.60"))
    assert (fallback.model_id, fallback.price_basis, fallback.listed_on) == ("azure/gpt-4o", "unknown_model", None)
    assert (fallback.input_usd_per_million, fallback.output_usd_per_million) == (Decimal("3.000"), Decimal("12.00"))
    assert (llm.configured, llm.fallback_enabled, llm.phrasing) == (True, True, True)
    assert (llm.daily_budget_usd, llm.session_token_limit) == (Decimal(10), 200000)
    active = {str(use.prompt) for use in container.model_inventory.prompts if use.active}
    assert "phrase_response@1" in active
    assert "summarize_for_handoff@1" not in active
    document = container.model_inventory.model_dump_json()
    for hidden in (secret, base, "private-endpoint", str(tmp_path), "api_key", "api_base"):
        assert hidden not in document


def test_without_the_credit_catalog_credit_is_not_enabled_and_injected_parts_are_left_out() -> None:
    settings = load_settings(env_file=None)

    class Unnamed:
        """A retriever adapter that declares no model."""

    inventory = build_model_inventory(
        settings,
        served={},
        retriever=Unnamed(),  # type: ignore[arg-type]
        llm=LlmHealth(),
        prompts=(),
        policy_pack_version="pack-test",
        credit_catalog_available=False,
        now=STARTED,
    )
    assert WorkflowId.CREDIT not in inventory.workflows_enabled
    assert [item.component for item in inventory.components] == [ModelComponent.LANGUAGE_DETECTOR]
    assert len(inventory.prompts) == 7
