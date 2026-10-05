"""What the running process serves, and the published offline evidence behind it (``GET /v1/eval/models``).

Two parts, both free of customer data:

- ``ModelInventory`` is configuration recorded while the composition root builds the process: which router,
  resolver, risk estimator, retriever, and language detector serve (a concrete ``ModelRef``, never an alias), whether
  a learned model fell back to its baseline and why (a reason code, never a path or a message), the language model
  setup (model ids, the price basis of each, the feature flags, the budget limits), the prompt versions, the policy
  pack version, and the enabled workflows. It never holds API keys, base URLs, file system paths, or identifiers.
- ``ModelCardSet`` is a curated copy of the published model cards and generated evaluation reports
  (``services/api/config/model_cards.yaml``): offline metrics on held-out splits of synthetic data with their 95%
  intervals, and the end-to-end promotion decisions measured in simulation. Every card names the repository files its
  numbers come from, the commit, and the generation time. Nothing here is a production measurement.
"""

from datetime import date
from decimal import Decimal
from math import isfinite
from typing import Annotated, Final, Literal, Self

from pydantic import Field, PositiveInt, StringConstraints, model_validator

from bank_agent.domain.base import Code, DomainModel, UtcDatetime
from bank_agent.domain.evaluation import GitSha, MetricCount, RepositoryPath, RunId
from bank_agent.domain.intelligence import ModelComponent, ModelId, ModelRef, PromptRef
from bank_agent.domain.workflow import WorkflowId

MODEL_CARDS_SCHEMA_VERSION: Final = "1.0.0"
Selection = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}@[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]
"""A configured selection, ``name@version_or_alias`` (``keyword@1``, ``tfidf@champion``)."""
ConfiguredModel = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}:[a-z][a-z0-9_]{0,63}@[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"),
]
"""A model as a run configured it, ``component:name@version_or_alias``; an alias appears only as its source wrote it."""
ModelKind = Literal["baseline", "learned", "unavailable"]
FallbackReason = Literal["artifact_not_found", "model_unavailable", "registry_unreadable"]
PriceBasisCode = Literal["verified", "unverified", "unknown_model"]
LlmRole = Literal["primary", "fallback"]
PromptPurpose = Literal["understanding", "phrasing", "handoff_summary", "not_called_by_engine"]
CardRole = Literal["default", "champion", "candidate", "reference"]
CardKind = Literal["offline", "provisional"]
MetricUnit = Literal["ratio", "ms"]
_UsdPerMillion = Annotated[Decimal, Field(ge=0)]


def _relative(path: str) -> bool:
    return not path.startswith("/") and ".." not in path


class ServedModel(DomainModel):
    """One component as the process serves it.

    ``selected`` is the configured selection; ``served`` the concrete model (``None`` when nothing serves, as for a
    risk estimator that could not load without the band fallback). ``alias`` is the alias the selection named when it
    differs from the served version. A component that ``fell_back`` names the reason code.
    """

    component: ModelComponent
    selected: Selection
    served: ModelRef | None
    kind: ModelKind
    alias: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")] | None = None
    fell_back: bool = False
    reason: FallbackReason | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.fell_back != (self.reason is not None):
            raise ValueError("a component that fell back names its reason, and only then")
        if (self.kind == "unavailable") != (self.served is None):
            raise ValueError("a component is unavailable exactly when nothing serves it")
        if self.served is not None and self.served.component is not self.component:
            raise ValueError("the served model belongs to the component")
        return self


class LlmModelSetup(DomainModel):
    """A configured language model and the price the budget guard and the cost metrics charge for it.

    The prices are the effective ones (``adapters/llm/prices.py``): as listed when ``verified``, times the
    unverified multiplier when ``unverified``, and the table's highest prices times the multiplier for an
    ``unknown_model``. ``listed_on`` is the date the listed price was read (``None`` for an unknown model).
    """

    role: LlmRole
    model_id: ModelId
    price_basis: PriceBasisCode
    input_usd_per_million: _UsdPerMillion
    output_usd_per_million: _UsdPerMillion
    listed_on: date | None = None


class LlmConfiguration(DomainModel):
    """The language model gateway as configured: provider, models, feature flags, and budget limits.

    ``configured`` is false when no provider is set up (``LLM_PROVIDER=fake`` without an injected client): every
    model call is refused and the workflows answer on their deterministic paths.
    """

    provider: Code
    configured: bool
    models: tuple[LlmModelSetup, ...]
    fallback_enabled: bool
    understanding: bool
    phrasing: bool
    handoff_summary: bool
    daily_budget_usd: Annotated[Decimal, Field(ge=0)]
    conversation_budget_usd: Annotated[Decimal, Field(ge=0)]
    session_token_limit: PositiveInt
    unverified_price_multiplier: Annotated[Decimal, Field(ge=1)]

    @model_validator(mode="after")
    def _validate(self) -> Self:
        roles = [item.role for item in self.models]
        if len(set(roles)) != len(roles):
            raise ValueError("each language model role appears once")
        if self.configured != ("primary" in roles):
            raise ValueError("a configured gateway names its primary model, and only then")
        if self.fallback_enabled and "fallback" not in roles:
            raise ValueError("an enabled fallback names its model")
        return self


class PromptUse(DomainModel):
    """A registered prompt version, what the engine calls it for, and whether the current flags let it run."""

    prompt: PromptRef
    purpose: PromptPurpose
    active: bool

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.purpose == "not_called_by_engine" and self.active:
            raise ValueError("a prompt the engine never calls is never active")
        return self


class ModelInventory(DomainModel):
    """The process's served models and configuration, recorded once at startup (``generated_at``)."""

    generated_at: UtcDatetime
    components: tuple[ServedModel, ...]
    llm: LlmConfiguration
    prompts: tuple[PromptUse, ...]
    policy_pack_version: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    workflows_enabled: tuple[WorkflowId, ...]

    @model_validator(mode="after")
    def _validate(self) -> Self:
        components = [item.component for item in self.components]
        if len(set(components)) != len(components):
            raise ValueError("each component is listed once")
        prompts = [str(item.prompt) for item in self.prompts]
        if len(set(prompts)) != len(prompts):
            raise ValueError("each prompt version is listed once")
        return self


class CardMetric(DomainModel):
    """One published metric with its 95% interval when the report gives one."""

    name: Code
    value: Annotated[float, Field(allow_inf_nan=False)]
    low: Annotated[float, Field(allow_inf_nan=False)] | None = None
    high: Annotated[float, Field(allow_inf_nan=False)] | None = None
    unit: MetricUnit = "ratio"

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if (self.low is None) != (self.high is None):
            raise ValueError("an interval has both bounds or none")
        if self.low is not None and self.high is not None and not self.low <= self.value <= self.high:
            raise ValueError("the value lies inside its interval")
        if self.unit == "ratio" and not all(0.0 <= item <= 1.0 for item in self._numbers()):
            raise ValueError("a ratio lies between 0 and 1")
        if self.unit == "ms" and not all(item >= 0.0 for item in self._numbers()):
            raise ValueError("a duration is not negative")
        return self

    def _numbers(self) -> tuple[float, ...]:
        return tuple(item for item in (self.value, self.low, self.high) if item is not None and isfinite(item))


class ModelCard(DomainModel):
    """The offline test (or dev) metrics of one model, copied from a generated report.

    ``kind`` is ``offline`` for labels made by construction or from the data, ``provisional`` while team-authored
    labels await human review. ``note`` qualifies the role, for example ``promotion_refused`` or
    ``needs_ml_extra`` (the model cannot run in the API image). ``use`` names the task slice (``dispute``).
    """

    component: ModelComponent
    model: ModelRef
    role: CardRole
    note: Code | None = None
    use: Code | None = None
    split: Literal["test", "dev"]
    sample_size: PositiveInt
    sample_unit: Literal["items", "queries", "customers"]
    kind: CardKind
    metrics: Annotated[tuple[CardMetric, ...], Field(min_length=1)]
    source: RepositoryPath
    report: RepositoryPath
    generated_at: UtcDatetime
    git_sha: GitSha

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.model.component is not self.component:
            raise ValueError("the card's model belongs to its component")
        if not (_relative(self.source) and _relative(self.report)):
            raise ValueError("sources are relative paths inside the repository")
        names = [metric.name for metric in self.metrics]
        if len(set(names)) != len(names):
            raise ValueError("each metric appears once per card")
        return self


class PromotionRow(DomainModel):
    """One configuration of an end-to-end comparison, with the counts its intervals are computed from."""

    run_id: RunId | None = None
    git_sha: GitSha | None = None
    models: Annotated[tuple[ConfiguredModel, ...], Field(min_length=1)]
    served: bool
    cases: PositiveInt
    safe_automated_resolution: MetricCount
    unsafe_outcomes: MetricCount
    escalation_unnecessary: MetricCount | None = None
    escalation_missed: MetricCount | None = None
    routing_correct: MetricCount | None = None

    @model_validator(mode="after")
    def _validate(self) -> Self:
        for metric in (self.safe_automated_resolution, self.unsafe_outcomes, self.routing_correct):
            if metric is not None and metric.denominator != self.cases:
                raise ValueError("case-level counts are over the row's cases")
        return self


class PromotionDecision(DomainModel):
    """A pre-registered default decision: the configurations compared end to end, which one serves, and why.

    The comparison is a simulation (simulated customers and a grader), on the dev split, with the language model
    named by ``language_model``; it is never a production measurement.
    """

    decision: Code
    outcome: Code
    reason: Code
    workflows: Annotated[tuple[WorkflowId, ...], Field(min_length=1)]
    split: Literal["dev", "test"]
    measurement: Literal["simulated"]
    language_model: ModelId
    session: Code
    rows: Annotated[tuple[PromotionRow, ...], Field(min_length=2)]
    source: RepositoryPath

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if sum(row.served for row in self.rows) != 1:
            raise ValueError("exactly one configuration of a decision serves")
        if not _relative(self.source):
            raise ValueError("the source is a relative path inside the repository")
        return self


class ModelCardSet(DomainModel):
    """The curated model cards and promotion decisions; empty when no file is published."""

    schema_version: Literal["1.0.0"] = MODEL_CARDS_SCHEMA_VERSION
    measurement: Literal["offline"] = "offline"
    data: Literal["synthetic"] = "synthetic"
    cards: tuple[ModelCard, ...] = ()
    promotions: tuple[PromotionDecision, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> Self:
        keys = [(card.model, card.use, card.split) for card in self.cards]
        if len(set(keys)) != len(keys):
            raise ValueError("each (model, use, split) card appears once")
        return self


EMPTY_CARD_SET: Final = ModelCardSet()
