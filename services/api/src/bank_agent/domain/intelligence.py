"""Inputs and outputs of the replaceable intelligence components.

The intent router, transaction resolver, language detector, retriever, model registry, prompt registry, and
language model client are ports. These models are what they exchange. Scores and confidences are floats
(they are probabilities, not money). Records always store a resolved ``ModelRef`` with a concrete version,
never only an alias such as ``champion``.
"""

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    Field,
    GetJsonSchemaHandler,
    JsonValue,
    NonNegativeInt,
    PositiveInt,
    StringConstraints,
    model_serializer,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from bank_agent.domain.base import DomainModel, Pii, UntrustedText
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.identifiers import ConversationId, LineageId, TransactionId, TurnId
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.money import Amount, Currency, Money
from bank_agent.domain.transaction import TransactionChannel
from bank_agent.domain.workflow import Intent

Probability = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
Score = Annotated[float, Field(allow_inf_nan=False)]
_NAME = r"[a-z][a-z0-9_]{0,63}"
_VERSION = r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}"


class ModelComponent(StrEnum):
    ROUTER = "router"
    RESOLVER = "resolver"
    RETRIEVER = "retriever"
    LANGUAGE_DETECTOR = "language_detector"
    LLM = "llm"
    RISK_ESTIMATOR = "risk_estimator"


MODEL_REF_PATTERN = rf"^({'|'.join(component.value for component in ModelComponent)}):{_NAME}@{_VERSION}$"
PROMPT_REF_PATTERN = rf"^{_NAME}@[1-9][0-9]*$"


class ModelRef(DomainModel):
    """A model implementation at a concrete version, serialized as ``router:tfidf@3``."""

    component: ModelComponent
    name: Annotated[str, StringConstraints(pattern=rf"^{_NAME}$")]
    version: Annotated[str, StringConstraints(pattern=rf"^{_VERSION}$")]

    @model_validator(mode="before")
    @classmethod
    def _parse_string(cls, value: object) -> object:
        if isinstance(value, str):
            match = re.fullmatch(r"([^:]+):([^@]+)@(.+)", value)
            if match is None:
                raise ValueError("a model reference has the form component:name@version")
            return {"component": match[1], "name": match[2], "version": match[3]}
        return value

    @model_serializer(mode="plain", when_used="always")
    def _serialize(self) -> str:
        return str(self)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler, /) -> JsonSchemaValue:
        return {"type": "string", "pattern": MODEL_REF_PATTERN, "title": "ModelRef"}

    def __str__(self) -> str:
        return f"{self.component.value}:{self.name}@{self.version}"


class PromptRef(DomainModel):
    """A prompt file at an exact version, serialized as ``extract_dispute_slots@2``."""

    prompt_id: Annotated[str, StringConstraints(pattern=rf"^{_NAME}$")]
    version: PositiveInt

    @model_validator(mode="before")
    @classmethod
    def _parse_string(cls, value: object) -> object:
        if isinstance(value, str):
            prompt_id, separator, version = value.rpartition("@")
            if not separator or not re.fullmatch(r"[1-9][0-9]*", version):
                raise ValueError("a prompt reference has the form prompt_id@version")
            return {"prompt_id": prompt_id, "version": int(version)}
        return value

    @model_serializer(mode="plain", when_used="always")
    def _serialize(self) -> str:
        return str(self)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler, /) -> JsonSchemaValue:
        return {"type": "string", "pattern": PROMPT_REF_PATTERN, "title": "PromptRef"}

    def __str__(self) -> str:
        return f"{self.prompt_id}@{self.version}"


# --- Intent routing ------------------------------------------------------------------------------------------


class IntentScore(DomainModel):
    intent: Intent
    score: Probability


class IntentPrediction(DomainModel):
    intent: Intent
    confidence: Probability
    candidates: Annotated[tuple[IntentScore, ...], Field(max_length=7)] = ()
    below_threshold: bool
    model: ModelRef


# --- Language detection --------------------------------------------------------------------------------------


class LanguageScore(DomainModel):
    language: Language
    score: Probability


class LanguageDetection(DomainModel):
    """``language`` is ``None`` when the detector is uncertain; the engine then asks the customer."""

    language: Language | None
    confidence: Probability
    candidates: tuple[LanguageScore, ...] = ()
    is_mixed: bool = False
    detector: ModelRef


# --- Transaction resolution ----------------------------------------------------------------------------------


class DateRange(DomainModel):
    """An inclusive range of calendar dates in the customer's time zone."""

    start: date
    end: date

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.end < self.start:
            raise ValueError("a date range cannot end before it starts")
        return self


class TransactionDescriptor(DomainModel):
    """What the customer said about the transaction. Every field is optional: unknown stays ``None``.

    ``date_interpretations`` holds zero ranges (no date given), one (resolved), or several (ambiguous, such
    as ``03/04``); the workflow asks the customer when there are several.
    """

    amount: Annotated[Amount, Field(ge=0)] | None = None
    currency_hint: Currency | None = None
    merchant_text: Annotated[UntrustedText, StringConstraints(max_length=150)] | None = None
    date_expression: Annotated[UntrustedText, StringConstraints(max_length=100)] | None = None
    date_interpretations: Annotated[tuple[DateRange, ...], Field(max_length=4)] = ()
    channel_hint: TransactionChannel | None = None
    card_last4_hint: Annotated[str, StringConstraints(pattern=r"^[0-9]{4}$")] | None = None

    @property
    def resolved_date_range(self) -> DateRange | None:
        return self.date_interpretations[0] if len(self.date_interpretations) == 1 else None

    @property
    def date_is_ambiguous(self) -> bool:
        return len(self.date_interpretations) > 1


class RankedCandidate(DomainModel):
    transaction_id: TransactionId
    score: Score
    rank: PositiveInt


class TransactionResolution(DomainModel):
    """Candidates ranked best first. ``clear_winner`` is set only when the top candidate beats the margin."""

    ranked: tuple[RankedCandidate, ...]
    margin: Score | None = None
    clear_winner: TransactionId | None = None
    model: ModelRef

    @model_validator(mode="after")
    def _validate(self) -> Self:
        ids = [candidate.transaction_id for candidate in self.ranked]
        if len(ids) != len(set(ids)):
            raise ValueError("a transaction can be ranked only once")
        if [candidate.rank for candidate in self.ranked] != list(range(1, len(self.ranked) + 1)):
            raise ValueError("ranks must be 1, 2, 3, and so on, in order")
        if self.clear_winner is not None and (not self.ranked or self.ranked[0].transaction_id != self.clear_winner):
            raise ValueError("the clear winner must be the top-ranked candidate")
        return self


# --- Retrieval -----------------------------------------------------------------------------------------------


class RetrievalQuery(DomainModel):
    text: Annotated[UntrustedText, StringConstraints(min_length=1, max_length=2000)]
    language: Language
    jurisdiction: Country
    k: Annotated[int, Field(ge=1, le=20)] = 5


class RetrievalHit(DomainModel):
    clause: ClauseRef
    score: Score
    rank: PositiveInt


class RetrievalResult(DomainModel):
    hits: tuple[RetrievalHit, ...]
    retriever: ModelRef


# --- Model registry ------------------------------------------------------------------------------------------


class ResolvedArtifact(DomainModel):
    ref: ModelRef
    local_path: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


# --- Language model client and prompts -----------------------------------------------------------------------

PromptValue = str | int | bool | Decimal | Money | None | Sequence[str]
"""A prompt variable. Untrusted text is passed as ``UntrustedText`` and the prompt file marks it as data."""

ModelId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")]


class TokenUsage(DomainModel):
    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens, output_tokens=self.output_tokens + other.output_tokens
        )


def _canonical(value: PromptValue) -> JsonValue:
    if isinstance(value, Money):
        return {"amount": str(value.amount), "currency": value.currency.value}
    if isinstance(value, Decimal):
        return str(value)
    if value is None or isinstance(value, str | int | bool):
        return value
    return [str(item) for item in value]


def canonical_variables(variables: Mapping[str, PromptValue]) -> str:
    """Canonical JSON for ``variables``: sorted keys, Decimal and Money as strings, no whitespace."""
    normalized = {key: _canonical(value) for key, value in variables.items()}
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def input_hash(prompt: PromptRef, variables: Mapping[str, PromptValue]) -> str:
    """SHA-256 over the prompt reference and the canonical variables: the key ``FakeLLM`` scripts use."""
    payload = f"{prompt}\n{canonical_variables(variables)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


SensitiveTerm = Annotated[str, StringConstraints(min_length=2, max_length=80)]


class LlmCallContext(DomainModel):
    """Who a call is for, so the budget guard can enforce per-session and per-conversation caps.

    ``sensitive_terms`` lists words the redaction decorator must mask wherever they appear in a variable, such
    as the session customer's first name. It never leaves the gateway: providers and cassettes never see it.
    """

    lineage_id: LineageId | None = None
    conversation_id: ConversationId | None = None
    turn_id: TurnId | None = None
    sensitive_terms: Annotated[tuple[SensitiveTerm, ...], Pii("name"), Field(max_length=10)] = ()


class TextGeneration(DomainModel):
    text: str
    usage: TokenUsage
    latency_ms: NonNegativeInt
    model_id: ModelId
    provider_model_id: str | None = None
    prompt: PromptRef
    cost_usd: Annotated[Amount, Field(ge=0)] | None = None
    model_call_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{16}$")] | None = None


class StructuredGeneration[OutputT: BaseModel](DomainModel):
    """A parsed structured output. ``repaired`` is true when the single repair attempt was needed."""

    value: OutputT
    usage: TokenUsage
    latency_ms: NonNegativeInt
    model_id: ModelId
    provider_model_id: str | None = None
    prompt: PromptRef
    repaired: bool = False
    cost_usd: Annotated[Amount, Field(ge=0)] | None = None
    model_call_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{16}$")] | None = None


class PromptVariableSpec(DomainModel):
    type: Literal["str", "int", "bool", "decimal", "money", "list_str"]
    required: bool = True
    untrusted: bool = False
    """Untrusted variables are wrapped in data delimiters when the prompt is rendered."""
    description: Annotated[str, StringConstraints(max_length=300)] = ""


class PromptChange(DomainModel):
    version: PositiveInt
    change: Annotated[str, StringConstraints(min_length=1, max_length=500)]


class PromptTemplate(DomainModel):
    """A loaded prompt file. ``output_model`` names a model in ``domain.llm_outputs.OUTPUT_MODELS``; ``None``
    means the prompt produces plain text. ``body`` holds the ``## System`` and ``## User`` sections."""

    ref: PromptRef
    purpose: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    variables: dict[Annotated[str, StringConstraints(pattern=rf"^{_NAME}$")], PromptVariableSpec]
    output_model: Annotated[str, StringConstraints(max_length=200)] | None = None
    owner: Annotated[str, StringConstraints(min_length=1, max_length=100)] = "unassigned"
    changelog: tuple[PromptChange, ...] = ()
    body: str


class PromptMessage(DomainModel):
    role: Literal["system", "user"]
    content: str


class RenderedPrompt(DomainModel):
    ref: PromptRef
    messages: tuple[PromptMessage, ...]
