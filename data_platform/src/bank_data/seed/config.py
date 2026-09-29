"""The persona file (``data_platform/seed/personas.yaml``): criteria and coverage, never customer data."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from bank_data.settings import DATA_PLATFORM_ROOT

DEFAULT_PERSONAS_FILE = DATA_PLATFORM_ROOT / "seed" / "personas.yaml"
DEFAULT_SAMPLE_PERSONAS_FILE = DATA_PLATFORM_ROOT / "seed" / "personas.sample.yaml"
WorkflowName = Literal["account_inquiry", "card_support", "dispute", "credit"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CustomerPersona(_Strict):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    criterion: str
    country: Literal["MX", "CO", "AR"]
    workflows: tuple[WorkflowName, ...] = Field(min_length=1)
    demonstrates: str
    seeded_case: bool = False
    seeded_application: bool = False


class StaffPersona(_Strict):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    staff_id: str
    role: Literal["agent", "evaluator"]
    display_name: str


class Coverage(_Strict):
    min_customers_per_country: int = Field(ge=0)
    every_segment: bool


class PersonaFile(_Strict):
    version: int
    seed: str
    customers: tuple[CustomerPersona, ...]
    staff: tuple[StaffPersona, ...]
    coverage: Coverage


def load_personas(path: Path = DEFAULT_PERSONAS_FILE) -> PersonaFile:
    return PersonaFile.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
