"""Analysis inputs: the reason-to-workflow mapping, the pre-registered scoring, and the cost assumptions.

All three are committed files (``data_platform/mappings/workflow_mapping.csv``,
``data_platform/analysis/scoring.yaml``, ``data_platform/analysis/cost_assumptions.yaml``), parsed into frozen,
validated models. The scoring file was committed before any result was computed
(``docs/analysis/workflow-scoring-preregistration.md``).
"""

import csv
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from bank_data.errors import ConfigurationError
from bank_data.settings import DATA_PLATFORM_ROOT

WORKFLOWS: tuple[str, ...] = ("account_inquiry", "card_support", "dispute", "credit")
"""The in-scope ``WorkflowId`` values (CLAUDE.md section 1), in their canonical order."""
OTHER = "other"
CRITERIA: tuple[str, ...] = ("demand", "pain", "automatable_share", "harm_inverse", "data_support", "demo_depth")
SCENARIOS: tuple[str, ...] = ("primary", "strict", "alternative")
MAPPING_SOURCES: tuple[str, ...] = ("contact_reason", "reason_category", "complaint_category")
DEMO_BEHAVIORS: tuple[str, ...] = (
    "read_path",
    "verified_write",
    "clause_abstention",
    "human_escalation",
    "workflow_learned_component",
)

DEFAULT_MAPPING_FILE = DATA_PLATFORM_ROOT / "mappings" / "workflow_mapping.csv"
DEFAULT_SCORING_FILE = DATA_PLATFORM_ROOT / "analysis" / "scoring.yaml"
DEFAULT_COST_FILE = DATA_PLATFORM_ROOT / "analysis" / "cost_assumptions.yaml"

Scenario = Literal["primary", "strict", "alternative"]
_TARGETS = (*WORKFLOWS, OTHER)
_MAPPING_COLUMNS = (
    "source",
    "value",
    "subcategory",
    "workflow_id",
    "sub_intent",
    "strict_workflow_id",
    "alternative_workflow_id",
    "rationale",
)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --------------------------------------------------------------------------------------------- mapping


class MappingRow(_Frozen):
    source: str
    value: str
    subcategory: str = ""
    workflow_id: str
    sub_intent: str = ""
    strict_workflow_id: str
    alternative_workflow_id: str
    rationale: str = Field(min_length=10)

    @model_validator(mode="after")
    def _validate(self) -> "MappingRow":
        if self.source not in MAPPING_SOURCES:
            raise ValueError(f"unknown mapping source {self.source!r}")
        for workflow in (self.workflow_id, self.strict_workflow_id, self.alternative_workflow_id):
            if workflow not in _TARGETS:
                raise ValueError(f"unknown workflow {workflow!r} for {self.value!r}")
        if self.sub_intent and self.workflow_id == OTHER:
            raise ValueError(f"{self.value!r} maps to other but names a sub-intent")
        if self.subcategory and self.source != "complaint_category":
            raise ValueError(f"only complaint rows carry a subcategory ({self.value!r})")
        return self

    def workflow_for(self, scenario: Scenario) -> str:
        if scenario == "strict":
            return self.strict_workflow_id
        if scenario == "alternative":
            return self.alternative_workflow_id
        return self.workflow_id


class WorkflowMapping(_Frozen):
    rows: tuple[MappingRow, ...]

    @model_validator(mode="after")
    def _unique(self) -> "WorkflowMapping":
        keys = [(row.source, row.value, row.subcategory) for row in self.rows]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError(f"duplicate mapping rows: {duplicates}")
        return self

    def lookup(self, source: str, value: str, subcategory: str | None = None) -> MappingRow | None:
        wanted = (source, value.strip(), (subcategory or "").strip())
        for row in self.rows:
            if (row.source, row.value, row.subcategory) == wanted:
                return row
        return None

    def for_source(self, source: str) -> tuple[MappingRow, ...]:
        return tuple(row for row in self.rows if row.source == source)


def load_mapping(path: Path = DEFAULT_MAPPING_FILE) -> WorkflowMapping:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != _MAPPING_COLUMNS:
                raise ConfigurationError(f"{path.name} must have the columns {', '.join(_MAPPING_COLUMNS)}")
            records = list(reader)
    except OSError as error:
        raise ConfigurationError(f"cannot read the workflow mapping {path.name}: {type(error).__name__}") from None
    try:
        return WorkflowMapping(rows=tuple(MappingRow.model_validate(record) for record in records))
    except ValidationError as error:
        raise ConfigurationError(f"invalid workflow mapping {path.name}: {error}") from None


# --------------------------------------------------------------------------------------------- scoring


class SensitivityConfig(_Frozen):
    delta_points: float = Field(gt=0, lt=50)


class PrioritizationConfig(_Frozen):
    tie_margin_points: float = Field(ge=0)
    subintent_data_support_threshold: float = Field(ge=0, le=1)


class StatisticsConfig(_Frozen):
    bootstrap_resamples: int = Field(ge=100, le=100_000)
    bootstrap_seed: int
    confidence: float = Field(gt=0.5, lt=1)
    small_cell_interactions: int = Field(ge=1)
    small_cell_surveys: int = Field(ge=1)


class LabelsConfig(_Frozen):
    target_per_workflow: int = Field(ge=1)
    documented_floor_per_workflow: int = Field(ge=1)
    min_matching_labels_per_workflow: int = Field(ge=1)
    seed: str = Field(min_length=1)


class DemandPatternsConfig(_Frozen):
    spike_window_days: int = Field(ge=7)
    spike_robust_z: float = Field(gt=0)
    error_contact_window_hours: int = Field(ge=1, le=168)
    baseline_sample_share: float = Field(gt=0, le=1)
    baseline_seed: str = Field(min_length=1)


class HarmRating(_Frozen):
    score: int = Field(ge=1, le=5)
    reason: str = Field(min_length=10)


class SubIntentSpec(_Frozen):
    workflow: str
    capability: float = Field(ge=0, le=1)
    harm: int = Field(ge=1, le=5)
    data_support: tuple[str, ...] = Field(min_length=1)


class ScoringConfig(_Frozen):
    version: int = Field(ge=1)
    preregistered_on: str
    weights: dict[str, float]
    sensitivity: SensitivityConfig
    prioritization: PrioritizationConfig
    statistics: StatisticsConfig
    labels: LabelsConfig
    demand_patterns: DemandPatternsConfig
    harm: dict[str, HarmRating]
    demo_depth: dict[str, dict[str, bool]]
    data_support: dict[str, tuple[str, ...]]
    sub_intents: dict[str, SubIntentSpec]

    @model_validator(mode="after")
    def _validate(self) -> "ScoringConfig":
        if set(self.weights) != set(CRITERIA):
            raise ValueError(f"weights must name exactly {', '.join(CRITERIA)}")
        if any(weight < 0 for weight in self.weights.values()) or sum(self.weights.values()) <= 0:
            raise ValueError("weights must be non-negative with a positive sum")
        for name, table in (("harm", self.harm), ("demo_depth", self.demo_depth), ("data_support", self.data_support)):
            if set(table) != set(WORKFLOWS):
                raise ValueError(f"{name} must rate exactly the four workflows")
        for workflow, behaviors in self.demo_depth.items():
            if set(behaviors) != set(DEMO_BEHAVIORS):
                raise ValueError(f"demo_depth of {workflow} must list {', '.join(DEMO_BEHAVIORS)}")
        for name, spec in self.sub_intents.items():
            if spec.workflow not in WORKFLOWS:
                raise ValueError(f"sub-intent {name} names an unknown workflow {spec.workflow!r}")
        missing = set(WORKFLOWS) - {spec.workflow for spec in self.sub_intents.values()}
        if missing:
            raise ValueError(f"workflows without sub-intents: {sorted(missing)}")
        return self

    def items_in_use(self) -> frozenset[str]:
        items = {item for values in self.data_support.values() for item in values}
        items.update(item for spec in self.sub_intents.values() for item in spec.data_support)
        return frozenset(items)


def load_scoring(path: Path = DEFAULT_SCORING_FILE) -> ScoringConfig:
    try:
        return ScoringConfig.model_validate(_read_yaml(path, "scoring configuration"))
    except ValidationError as error:
        raise ConfigurationError(f"invalid scoring configuration {path.name}: {error}") from None


# --------------------------------------------------------------------------------------------- cost


class CountryCost(_Frozen):
    loaded_cost_per_handled_minute: float = Field(gt=0)
    assumption: bool
    verified: bool
    source: str = Field(min_length=10)


class LabeledFactor(_Frozen):
    value: float = Field(gt=0)
    assumption: bool
    verified: bool
    source: str = Field(min_length=10)


class CostAssumptions(_Frozen):
    version: int = Field(ge=1)
    currency: str = Field(pattern="^[A-Z]{3}$")
    countries: dict[str, CountryCost]
    after_call_work_factor: LabeledFactor
    sensitivity_multipliers: tuple[float, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate(self) -> "CostAssumptions":
        unlabeled = [code for code, cost in self.countries.items() if not cost.assumption]
        if unlabeled or not self.after_call_work_factor.assumption:
            raise ValueError("every cost value is an assumption and must say so (assumption: true)")
        if any(multiplier <= 0 for multiplier in self.sensitivity_multipliers):
            raise ValueError("sensitivity multipliers must be positive")
        return self

    def cost_per_minute(self, country: str | None) -> float | None:
        if country is None or country not in self.countries:
            return None
        return self.countries[country].loaded_cost_per_handled_minute * self.after_call_work_factor.value


def load_costs(path: Path = DEFAULT_COST_FILE) -> CostAssumptions:
    try:
        return CostAssumptions.model_validate(_read_yaml(path, "cost assumptions"))
    except ValidationError as error:
        raise ConfigurationError(f"invalid cost assumptions {path.name}: {error}") from None


def _read_yaml(path: Path, what: str) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ConfigurationError(f"cannot read the {what} {path.name}: {type(error).__name__}") from None
