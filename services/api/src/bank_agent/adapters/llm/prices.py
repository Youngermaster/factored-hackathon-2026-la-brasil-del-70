"""The model price table and the cost of a call.

Prices live only in ``services/api/config/llm_prices.yaml``; no price is written in code. Each entry states the
model id (as configured for the gateway), input and output prices in US dollars per million tokens, the date the
price was read, the source URL, and whether a person has verified it against that source.

The effective price is conservative:

- a verified entry is used as written;
- an unverified entry is multiplied by ``unverified_price_multiplier`` (at least 1);
- a model missing from the table is charged at the highest input and the highest output price in the table,
  times the multiplier.

Costs are rounded up to eight decimal places, so rounding never understates spend.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final, Literal, Self

import yaml
from pydantic import Field, StringConstraints, ValidationError, model_validator

from bank_agent.domain.base import DomainModel
from bank_agent.domain.errors import ConfigurationError
from bank_agent.domain.intelligence import ModelId, TokenUsage
from bank_agent.domain.money import Amount

PER_MILLION: Final = Decimal(1_000_000)
COST_QUANTUM: Final = Decimal("0.00000001")
Price = Annotated[Amount, Field(ge=0)]


class PriceBasis(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    UNKNOWN_MODEL = "unknown_model"


class ModelPrice(DomainModel):
    model_id: ModelId
    input_usd_per_million: Price
    output_usd_per_million: Price
    effective_date: date
    source_url: Annotated[str, StringConstraints(pattern=r"^https://\S+$", max_length=500)]
    verified: bool
    notes: Annotated[str, StringConstraints(max_length=500)] = ""


class PriceTableFile(DomainModel):
    schema_version: Literal[1]
    currency: Literal["USD"]
    unverified_price_multiplier: Annotated[Amount, Field(ge=1)]
    models: Annotated[tuple[ModelPrice, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _unique(self) -> Self:
        ids = [entry.model_id for entry in self.models]
        if len(ids) != len(set(ids)):
            raise ValueError("a model id can appear only once")
        return self


@dataclass(frozen=True, slots=True)
class EffectivePrice:
    input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    basis: PriceBasis


class PriceTable:
    """Looks up effective prices and computes the cost of a call."""

    def __init__(self, table: PriceTableFile) -> None:
        self._table = table
        self._entries = {entry.model_id: entry for entry in table.models}

    @classmethod
    def from_yaml(cls, path: Path) -> "PriceTable":
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            return cls(PriceTableFile.model_validate(raw))
        except (OSError, yaml.YAMLError, ValidationError) as error:
            raise ConfigurationError(f"the price table {path.name} is missing or invalid") from error

    @property
    def entries(self) -> tuple[ModelPrice, ...]:
        return self._table.models

    @property
    def unverified_multiplier(self) -> Decimal:
        """The factor applied to unverified and unknown prices (at least 1)."""
        return self._table.unverified_price_multiplier

    def effective(self, model_id: str) -> EffectivePrice:
        multiplier = self._table.unverified_price_multiplier
        entry = self._entries.get(model_id)
        if entry is None:
            return EffectivePrice(
                max(item.input_usd_per_million for item in self._table.models) * multiplier,
                max(item.output_usd_per_million for item in self._table.models) * multiplier,
                PriceBasis.UNKNOWN_MODEL,
            )
        if entry.verified:
            return EffectivePrice(entry.input_usd_per_million, entry.output_usd_per_million, PriceBasis.VERIFIED)
        return EffectivePrice(
            entry.input_usd_per_million * multiplier,
            entry.output_usd_per_million * multiplier,
            PriceBasis.UNVERIFIED,
        )

    def cost(self, model_id: str, usage: TokenUsage) -> Decimal:
        price = self.effective(model_id)
        raw = (
            Decimal(usage.input_tokens) * price.input_usd_per_million
            + Decimal(usage.output_tokens) * price.output_usd_per_million
        ) / PER_MILLION
        return raw.quantize(COST_QUANTUM, rounding=ROUND_CEILING)

    def worst_output_cost(self, model_ids: tuple[str, ...], output_tokens: int) -> Decimal:
        """The highest cost of ``output_tokens`` among ``model_ids``: the budget guard's reservation."""
        prices = [self.effective(model_id).output_usd_per_million for model_id in model_ids or ("",)]
        return (Decimal(output_tokens) * max(prices) / PER_MILLION).quantize(COST_QUANTUM, rounding=ROUND_CEILING)
