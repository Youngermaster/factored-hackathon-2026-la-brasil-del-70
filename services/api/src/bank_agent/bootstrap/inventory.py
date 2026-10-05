"""Builds the model inventory the supervision view shows (``GET /v1/eval/models``), once, at startup.

Every field is configuration the composition root already holds: the models ``bootstrap/models.py`` recorded while
building the router, resolver, and risk estimator; the retriever and the language detector; the language model ids
the gateway resolved, with the effective price basis from the price table; the ``WORKFLOW_LLM_*`` flags and the budget
limits; the registered prompt versions; the policy pack version; and the enabled workflows. API keys, base URLs, file
system paths, and the Langfuse settings are never read here.
"""

from collections.abc import Iterable, Mapping
from datetime import datetime

from bank_agent.adapters.llm.prices import PriceTable
from bank_agent.adapters.models.lexical_language import LEXICAL_DETECTOR
from bank_agent.adapters.reliability.monitor import LlmHealth
from bank_agent.application.supervision.prompts import prompt_uses
from bank_agent.bootstrap.models import served_model
from bank_agent.bootstrap.settings import AppSettings
from bank_agent.bootstrap.workflows import enabled_workflows
from bank_agent.domain.intelligence import ModelComponent, ModelRef, PromptRef
from bank_agent.domain.model_inventory import LlmConfiguration, LlmModelSetup, LlmRole, ModelInventory, ServedModel
from bank_agent.domain.workflow import WorkflowId
from bank_agent.ports.retrieval import Retriever

COMPONENT_ORDER = (
    ModelComponent.ROUTER,
    ModelComponent.RESOLVER,
    ModelComponent.RISK_ESTIMATOR,
    ModelComponent.RETRIEVER,
    ModelComponent.LANGUAGE_DETECTOR,
)


def retriever_model(retriever: Retriever) -> ModelRef | None:
    """The retriever's model; the ``Retriever`` port declares none, so the built adapter's attribute is read."""
    model = getattr(retriever, "model", None)
    return model if isinstance(model, ModelRef) else None


def _llm_setup(role: LlmRole, model_id: str, prices: PriceTable) -> LlmModelSetup:
    price = prices.effective(model_id)
    listed = next((entry for entry in prices.entries if entry.model_id == model_id), None)
    return LlmModelSetup(
        role=role,
        model_id=model_id,
        price_basis=price.basis.value,
        input_usd_per_million=price.input_usd_per_million,
        output_usd_per_million=price.output_usd_per_million,
        listed_on=listed.effective_date if listed is not None else None,
    )


def llm_configuration(settings: AppSettings, health: LlmHealth) -> LlmConfiguration:
    """The gateway as built: ``health.primary`` is ``None`` when no provider is configured (every call refused)."""
    prices = PriceTable.from_yaml(settings.llm.prices_file)
    configured = health.primary is not None
    models: list[LlmModelSetup] = []
    if configured:
        models.append(_llm_setup("primary", health.primary_model, prices))
        if health.fallback_model:
            models.append(_llm_setup("fallback", health.fallback_model, prices))
    workflow = settings.workflow
    return LlmConfiguration(
        provider=settings.llm.provider,
        configured=configured,
        models=tuple(models),
        fallback_enabled=configured and bool(health.fallback_model),
        understanding=workflow.llm_understanding,
        phrasing=workflow.llm_phrasing,
        handoff_summary=workflow.llm_handoff_summary,
        daily_budget_usd=settings.llm.daily_budget_usd,
        conversation_budget_usd=settings.llm.conversation_budget_usd,
        session_token_limit=settings.llm.session_token_limit,
        unverified_price_multiplier=prices.unverified_multiplier,
    )


def build_model_inventory(
    settings: AppSettings,
    *,
    served: Mapping[ModelComponent, ServedModel],
    retriever: Retriever,
    llm: LlmHealth,
    prompts: Iterable[PromptRef],
    policy_pack_version: str,
    credit_catalog_available: bool,
    now: datetime,
) -> ModelInventory:
    """The inventory of one process. Components a caller injected instead of building are left out."""
    recorded = dict(served)
    retrieval = retriever_model(retriever)
    if retrieval is not None:
        selection = f"{settings.retrieval.retriever}@{retrieval.version}"
        recorded[ModelComponent.RETRIEVER] = served_model(ModelComponent.RETRIEVER, selection, retrieval)
    recorded[ModelComponent.LANGUAGE_DETECTOR] = served_model(
        ModelComponent.LANGUAGE_DETECTOR, settings.workflow.language_detector, LEXICAL_DETECTOR
    )
    enabled = enabled_workflows(settings.workflow)
    if not credit_catalog_available:
        enabled = enabled - {WorkflowId.CREDIT}
    configuration = llm_configuration(settings, llm)
    return ModelInventory(
        generated_at=now,
        components=tuple(recorded[component] for component in COMPONENT_ORDER if component in recorded),
        llm=configuration,
        prompts=prompt_uses(
            prompts,
            model_configured=configuration.configured,
            understanding=settings.workflow.llm_understanding,
            phrasing=settings.workflow.llm_phrasing,
            handoff_summary=settings.workflow.llm_handoff_summary,
        ),
        policy_pack_version=policy_pack_version,
        workflows_enabled=tuple(workflow for workflow in WorkflowId if workflow in enabled),
    )
