"""Record and replay of language model calls, for deterministic tests and evaluations.

A cassette is one JSON file per call at ``<directory>/<prompt_id>/<version>/<key>.json``. The key is a SHA-256
over the prompt reference, the model id, the session language, and the canonical JSON of the redacted
variables. The language is part of the key because the same variables in Spanish and in Portuguese must give
different replies.

Variables are redacted (``Redactor``, idempotent) before they are hashed, forwarded, or written, and the output
is redacted before it is written, so a cassette never holds personal data. In replay mode a missing cassette
raises ``CassetteMissingError``, a configuration error outside the LLM error family, so it fails the run loudly
instead of being absorbed by a caller's fallback; replay never calls a provider. Record mode requires an inner
client and overwrites the cassette for the same key.

``provenance`` is ``recorded`` for a real provider reply and ``hand_authored_fixture`` for a file written by a
person; fixtures also use the model id ``fixture/hand-authored`` so they can never be mistaken for evidence of
model quality.
"""

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, Field, JsonValue, NonNegativeInt, StringConstraints, ValidationError

from bank_agent.adapters.llm.redaction import Redactor
from bank_agent.domain.base import DomainModel, UtcDatetime
from bank_agent.domain.errors import ConfigurationError, LlmInvalidOutputError
from bank_agent.domain.intelligence import (
    LlmCallContext,
    PromptRef,
    PromptValue,
    StructuredGeneration,
    TextGeneration,
    TokenUsage,
    canonical_variables,
)
from bank_agent.domain.locale import Language
from bank_agent.ports.determinism import Clock
from bank_agent.ports.llm import LLMClient

CASSETTE_SCHEMA_VERSION: Final = 1
FIXTURE_MODEL_ID: Final = "fixture/hand-authored"


class CassetteMode(StrEnum):
    REPLAY = "replay"
    RECORD = "record"


class Provenance(StrEnum):
    RECORDED = "recorded"
    HAND_AUTHORED_FIXTURE = "hand_authored_fixture"


class CassetteMissingError(ConfigurationError):
    """Replay found no cassette for a call. Record it, or fix the call; never silently call a provider."""

    code = "llm_cassette_missing"


class CassetteMismatchError(ConfigurationError):
    """A cassette exists for the key but does not fit the call (kind, output model, or content)."""

    code = "llm_cassette_mismatch"


class Cassette(DomainModel):
    schema_version: Literal[1] = CASSETTE_SCHEMA_VERSION
    cassette_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    """The cassette key; named ``cassette_id`` so secret scanners do not mistake the hash for a credential."""
    provenance: Provenance
    note: Annotated[str, StringConstraints(max_length=500)] = ""
    labels: dict[str, str] = Field(default_factory=dict)
    prompt: PromptRef
    model_id: str
    language: Language
    kind: Literal["structured", "text"]
    output_model: str | None
    variables: dict[str, JsonValue]
    output: dict[str, JsonValue] | str
    usage: TokenUsage
    latency_ms: NonNegativeInt
    repaired: bool = False
    recorded_at: UtcDatetime


def cassette_key(prompt: PromptRef, model_id: str, language: Language, canonical: str) -> str:
    """The cassette key over the canonical JSON of the (already redacted) variables."""
    payload = f"{prompt}\n{model_id}\n{language.value}\n{canonical}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stored_key(cassette: Cassette) -> str:
    """Recompute a cassette's key from its own content (a hand-edited file must still match its name)."""
    canonical = json.dumps(cassette.variables, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return cassette_key(cassette.prompt, cassette.model_id, cassette.language, canonical)


def cassette_path(directory: Path, prompt: PromptRef, key: str) -> Path:
    return directory / prompt.prompt_id / str(prompt.version) / f"{key}.json"


def load_cassette(path: Path) -> Cassette:
    try:
        cassette = Cassette.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise CassetteMismatchError(f"{path.name}: not a valid cassette") from error
    if stored_key(cassette) != cassette.cassette_id or path.stem != cassette.cassette_id:
        raise CassetteMismatchError(f"{path.name}: the key does not match the content")
    return cassette


def write_cassette(path: Path, cassette: Cassette) -> None:
    """Write deterministically (sorted keys, two-space indent, trailing newline) and atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(cassette.model_dump(mode="json"), sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    handle, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(text)
    Path(temporary).replace(path)


class CassetteLLM:
    """Implements ``LLMClient`` by replaying cassettes, or by recording the replies of ``inner``."""

    def __init__(
        self,
        directory: Path,
        *,
        model_id: str,
        redactor: Redactor,
        clock: Clock,
        mode: CassetteMode = CassetteMode.REPLAY,
        inner: LLMClient | None = None,
    ) -> None:
        if not model_id:
            raise ConfigurationError("cassette replay needs a model id")
        if mode is CassetteMode.RECORD and inner is None:
            raise ConfigurationError("record mode needs an inner client")
        self.directory = directory
        self.model_id = model_id
        self.mode = mode
        self.inner = inner
        self._redactor = redactor
        self._clock = clock

    def _prepare(
        self, prompt: PromptRef, variables: Mapping[str, PromptValue], language: Language, context: LlmCallContext
    ) -> tuple[dict[str, PromptValue], str, Path]:
        redacted = self._redactor.redact_variables(variables, context.sensitive_terms)
        key = cassette_key(prompt, self.model_id, language, canonical_variables(redacted))
        return redacted, key, cassette_path(self.directory, prompt, key)

    def _replay(self, path: Path, prompt: PromptRef, kind: str, output_model: str | None) -> Cassette:
        if not path.is_file():
            raise CassetteMissingError(f"no cassette for {prompt} ({path.name}); record it or fix the call")
        cassette = load_cassette(path)
        if cassette.kind != kind or cassette.output_model != output_model:
            raise CassetteMismatchError(f"{path.name}: recorded as {cassette.kind} {cassette.output_model}")
        return cassette

    def _record(
        self,
        path: Path,
        key: str,
        prompt: PromptRef,
        language: Language,
        redacted: Mapping[str, PromptValue],
        output: dict[str, JsonValue] | str,
        generation: StructuredGeneration[Any] | TextGeneration,
        output_model: str | None,
        context: LlmCallContext,
    ) -> None:
        terms = context.sensitive_terms
        safe_output = self._redactor.redact_text(output, terms) if isinstance(output, str) else output
        if isinstance(safe_output, dict):
            redacted_output = self._redactor.redact_json(safe_output, terms)
            safe_output = redacted_output if isinstance(redacted_output, dict) else safe_output
        cassette = Cassette(
            cassette_id=key,
            provenance=Provenance.RECORDED,
            prompt=prompt,
            model_id=self.model_id,
            language=language,
            kind="text" if isinstance(output, str) else "structured",
            output_model=output_model,
            variables=json.loads(canonical_variables(redacted)),
            output=safe_output,
            usage=generation.usage,
            latency_ms=generation.latency_ms,
            repaired=isinstance(generation, StructuredGeneration) and generation.repaired,
            recorded_at=self._clock.now(),
        )
        write_cassette(path, cassette)

    async def generate_structured[OutputT: BaseModel](
        self,
        prompt: PromptRef,
        variables: Mapping[str, PromptValue],
        output_model: type[OutputT],
        *,
        language: Language,
        max_output_tokens: int,
        temperature: float,
        call_context: LlmCallContext,
    ) -> StructuredGeneration[OutputT]:
        redacted, key, path = self._prepare(prompt, variables, language, call_context)
        if self.mode is CassetteMode.RECORD and self.inner is not None:
            generation = await self.inner.generate_structured(
                prompt,
                redacted,
                output_model,
                language=language,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
                call_context=call_context,
            )
            output = generation.value.model_dump(mode="json")
            self._record(path, key, prompt, language, redacted, output, generation, output_model.__name__, call_context)
            return generation
        cassette = self._replay(path, prompt, "structured", output_model.__name__)
        try:
            value = output_model.model_validate(cassette.output)
        except ValidationError:
            raise LlmInvalidOutputError(f"{prompt}: the recorded output no longer fits the output model") from None
        return StructuredGeneration(
            value=value,
            usage=cassette.usage,
            latency_ms=cassette.latency_ms,
            model_id=cassette.model_id,
            prompt=prompt,
            repaired=cassette.repaired,
        )

    async def generate_text(
        self,
        prompt: PromptRef,
        variables: Mapping[str, PromptValue],
        *,
        language: Language,
        max_output_tokens: int,
        temperature: float,
        call_context: LlmCallContext,
    ) -> TextGeneration:
        redacted, key, path = self._prepare(prompt, variables, language, call_context)
        if self.mode is CassetteMode.RECORD and self.inner is not None:
            generation = await self.inner.generate_text(
                prompt,
                redacted,
                language=language,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
                call_context=call_context,
            )
            self._record(path, key, prompt, language, redacted, generation.text, generation, None, call_context)
            return generation
        cassette = self._replay(path, prompt, "text", None)
        if not isinstance(cassette.output, str):
            raise CassetteMismatchError(f"{path.name}: a text cassette must hold a string")
        return TextGeneration(
            text=cassette.output,
            usage=cassette.usage,
            latency_ms=cassette.latency_ms,
            model_id=cassette.model_id,
            prompt=prompt,
        )
