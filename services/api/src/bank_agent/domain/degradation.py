"""The degradation ladder: levels, component states, and the status the engine and the health probes read.

L0 is normal. L1: the primary language model provider is unavailable and the fallback provider serves. L2: no
provider can serve (or the daily model budget is spent), so replies are templates, understanding is deterministic,
and complex cases go to a person. L3: learned models or the credit catalog failed to load, so the baselines serve
with a stricter clarification budget. L4: the database is unavailable or read-only, so nothing is done and the API
answers 503 with ``Retry-After``. The reported level is the highest active one; each active condition applies its
own behavior. Writes never fail open at any level (``docs/operations/degradation.md``).
"""

from enum import IntEnum, StrEnum
from typing import Annotated

from pydantic import Field

from bank_agent.domain.base import Code, DomainModel


class DegradationLevel(IntEnum):
    NORMAL = 0
    FALLBACK_PROVIDER = 1
    TEMPLATE_ONLY = 2
    MODEL_BASELINES = 3
    DATABASE_UNAVAILABLE = 4

    @property
    def label(self) -> str:
        return f"L{self.value}"


class ComponentState(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    """Not configured on purpose (no language model provider, no database): a configuration, not a failure."""


class Component(StrEnum):
    LLM_PRIMARY = "llm_primary"
    LLM_FALLBACK = "llm_fallback"
    LLM_BUDGET = "llm_budget"
    MODELS = "models"
    CREDIT_CATALOG = "credit_catalog"
    DATABASE = "database"


class DegradationStatus(DomainModel):
    level: DegradationLevel = DegradationLevel.NORMAL
    reasons: tuple[Code, ...] = ()
    components: dict[Component, ComponentState] = Field(default_factory=dict)
    template_only: bool = False
    """L2 behavior is on: no model call is attempted this turn."""
    stricter_clarification: bool = False
    """L2 or L3: one clarifying question fewer before a handoff."""
    budget_used_ratio: Annotated[float, Field(ge=0)] = 0.0

    @property
    def degraded(self) -> bool:
        return self.level is not DegradationLevel.NORMAL


NORMAL = DegradationStatus()
