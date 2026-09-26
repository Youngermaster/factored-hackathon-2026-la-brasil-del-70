import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import JsonValue

from bank_agent.adapters.llm.cassette import (
    Cassette,
    CassetteLLM,
    CassetteMismatchError,
    CassetteMissingError,
    CassetteMode,
    Provenance,
    cassette_key,
    cassette_path,
    load_cassette,
    stored_key,
    write_cassette,
)
from bank_agent.adapters.llm.redaction import Redactor
from bank_agent.domain.errors import ConfigurationError, LlmInvalidOutputError
from bank_agent.domain.intelligence import LlmCallContext, TokenUsage, canonical_variables
from bank_agent.domain.llm_outputs import DisputeSlotExtraction, EscalationSignals
from bank_agent.domain.locale import Language
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.fake_llm import FakeLLM, ScriptedResponse
from bank_agent_llm import CONTEXT, DISPUTE_PROMPT, PHRASE_PROMPT, dispute_variables, phrase_variables

NOW = datetime(2026, 9, 26, 12, tzinfo=UTC)
MODEL = "test/recorded-model"
SLOTS: dict[str, JsonValue] = {
    "intent_candidates": [{"intent": "dispute_new", "confidence": 0.8}],
    "transaction": {
        "amount": "1500",
        "currency_hint": "MXN",
        "merchant_text": "Oxxo",
        "date_expression": None,
        "channel_hint": None,
        "card_last4_hint": None,
    },
    "reason_candidates": ["unrecognized"],
}


def _cassettes(root: Path) -> list[Path]:
    return sorted(root.rglob("*.json"))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _rewrite(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _recorder(tmp_path: Path, fake: FakeLLM) -> CassetteLLM:
    return CassetteLLM(
        tmp_path, model_id=MODEL, redactor=Redactor(), clock=FixedClock(NOW), mode=CassetteMode.RECORD, inner=fake
    )


def _player(tmp_path: Path, model_id: str = MODEL) -> CassetteLLM:
    return CassetteLLM(tmp_path, model_id=model_id, redactor=Redactor(), clock=FixedClock(NOW))


async def _extract(client: CassetteLLM, message: str, language: Language = Language.ES) -> DisputeSlotExtraction:
    result = await client.generate_structured(
        DISPUTE_PROMPT,
        dispute_variables(message),
        DisputeSlotExtraction,
        language=language,
        max_output_tokens=300,
        temperature=0.0,
        call_context=CONTEXT,
    )
    return result.value


async def test_record_then_replay_is_identical(tmp_path: Path) -> None:
    fake = FakeLLM()
    fake.script(DISPUTE_PROMPT, ScriptedResponse(SLOTS, usage=TokenUsage(input_tokens=90, output_tokens=30)))
    fake.script(PHRASE_PROMPT, ScriptedResponse("Su saldo disponible es 1200.00 MXN."))
    recorder = _recorder(tmp_path, fake)

    recorded = await _extract(recorder, "No reconozco un cargo de 1500 pesos en Oxxo")
    recorded_text = await recorder.generate_text(
        PHRASE_PROMPT,
        phrase_variables(),
        language=Language.ES,
        max_output_tokens=100,
        temperature=0.0,
        call_context=CONTEXT,
    )

    player = _player(tmp_path)
    replayed = await _extract(player, "No reconozco un cargo de 1500 pesos en Oxxo")
    replayed_text = await player.generate_text(
        PHRASE_PROMPT,
        phrase_variables(),
        language=Language.ES,
        max_output_tokens=100,
        temperature=0.0,
        call_context=CONTEXT,
    )

    assert replayed == recorded
    assert replayed_text.text == recorded_text.text
    assert replayed_text.model_id == MODEL
    files = _cassettes(tmp_path)
    assert len(files) == 2
    cassette = load_cassette(files[0])
    assert cassette.provenance is Provenance.RECORDED
    assert cassette.recorded_at == NOW
    assert cassette.usage.input_tokens in {0, 90}


async def test_replay_fails_loudly_when_the_cassette_is_missing(tmp_path: Path) -> None:
    with pytest.raises(CassetteMissingError, match="no cassette for extract_dispute_slots@1"):
        await _extract(_player(tmp_path), "mensaje sin cassette")

    assert not issubclass(CassetteMissingError, LlmInvalidOutputError)
    assert issubclass(CassetteMissingError, ConfigurationError)


async def test_the_key_depends_on_language_and_model(tmp_path: Path) -> None:
    fake = FakeLLM()
    fake.script(DISPUTE_PROMPT, ScriptedResponse(SLOTS))
    await _extract(_recorder(tmp_path, fake), "cargo raro")

    with pytest.raises(CassetteMissingError):
        await _extract(_player(tmp_path), "cargo raro", Language.PT)
    with pytest.raises(CassetteMissingError):
        await _extract(_player(tmp_path, model_id="other/model"), "cargo raro")


async def test_redacts_variables_before_forwarding_hashing_and_writing(tmp_path: Path) -> None:
    fake = FakeLLM()
    fake.script(PHRASE_PROMPT, ScriptedResponse("Listo, Mariana. Te escribimos a mariana@example.com."))
    recorder = _recorder(tmp_path, fake)
    context = LlmCallContext(sensitive_terms=("Mariana",))
    variables = phrase_variables(["Correo registrado: mariana@example.com", "Titular: Mariana"])

    live = await recorder.generate_text(
        PHRASE_PROMPT, variables, language=Language.ES, max_output_tokens=100, temperature=0.0, call_context=context
    )

    (path,) = _cassettes(tmp_path)
    text = _read(path)
    assert "mariana" not in text.lower()
    stored = json.loads(text)
    assert stored["variables"]["facts"] == ["Correo registrado: [EMAIL]", "Titular: [NAME]"]
    assert stored["output"] == "Listo, [NAME]. Te escribimos a [EMAIL]."
    assert fake.calls[0].variables["facts"] == ["Correo registrado: [EMAIL]", "Titular: [NAME]"]
    assert live.text.startswith("Listo, Mariana")

    replayed = await _player(tmp_path).generate_text(
        PHRASE_PROMPT, variables, language=Language.ES, max_output_tokens=100, temperature=0.0, call_context=context
    )
    assert replayed.text == "Listo, [NAME]. Te escribimos a [EMAIL]."


async def test_redacts_structured_output_before_writing(tmp_path: Path) -> None:
    fake = FakeLLM()
    leaky = dict(SLOTS, transaction=dict(SLOTS["transaction"], merchant_text="Pago a juan@example.com"))  # type: ignore[arg-type]
    fake.script(DISPUTE_PROMPT, ScriptedResponse(leaky))

    await _extract(_recorder(tmp_path, fake), "pago raro")

    (path,) = _cassettes(tmp_path)
    assert json.loads(_read(path))["output"]["transaction"]["merchant_text"] == "Pago a [EMAIL]"


async def test_the_written_file_is_deterministic_and_keyed_by_its_content(tmp_path: Path) -> None:
    fake = FakeLLM()
    fake.script(DISPUTE_PROMPT, ScriptedResponse(SLOTS))
    await _extract(_recorder(tmp_path, fake), "cargo raro")
    (path,) = _cassettes(tmp_path)
    first = _read(path)

    await _extract(_recorder(tmp_path, fake), "cargo raro")

    assert _read(path) == first
    assert first.endswith("}\n")
    cassette = load_cassette(path)
    assert stored_key(cassette) == cassette.key == path.stem
    assert path == cassette_path(tmp_path, DISPUTE_PROMPT, cassette.key)


def _fixture(tmp_path: Path, **changes: object) -> Path:
    variables = json.loads(canonical_variables(dispute_variables("hola")))
    key = cassette_key(DISPUTE_PROMPT, MODEL, Language.ES, canonical_variables(dispute_variables("hola")))
    data = {
        "key": key,
        "provenance": "hand_authored_fixture",
        "prompt": "extract_dispute_slots@1",
        "model_id": MODEL,
        "language": "es",
        "kind": "structured",
        "output_model": "DisputeSlotExtraction",
        "variables": variables,
        "output": SLOTS,
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "latency_ms": 0,
        "recorded_at": NOW.isoformat(),
    }
    data.update(changes)
    cassette = Cassette.model_validate(data)
    path = cassette_path(tmp_path, DISPUTE_PROMPT, key)
    write_cassette(path, cassette)
    return path


async def test_rejects_a_cassette_whose_content_does_not_match_its_key(tmp_path: Path) -> None:
    path = _fixture(tmp_path)
    data = json.loads(_read(path))
    data["variables"]["customer_message"] = "edited by hand"
    _rewrite(path, json.dumps(data))

    with pytest.raises(CassetteMismatchError, match="does not match"):
        await _extract(_player(tmp_path), "hola")


async def test_rejects_a_malformed_cassette(tmp_path: Path) -> None:
    path = _fixture(tmp_path)
    _rewrite(path, "{}")

    with pytest.raises(CassetteMismatchError, match="not a valid cassette"):
        await _extract(_player(tmp_path), "hola")


async def test_rejects_a_cassette_of_the_wrong_kind_or_output_model(tmp_path: Path) -> None:
    _fixture(tmp_path)

    with pytest.raises(CassetteMismatchError, match="recorded as structured"):
        await _player(tmp_path).generate_structured(
            DISPUTE_PROMPT,
            dispute_variables("hola"),
            EscalationSignals,
            language=Language.ES,
            max_output_tokens=10,
            temperature=0.0,
            call_context=CONTEXT,
        )
    with pytest.raises(CassetteMismatchError, match="recorded as structured"):
        await _player(tmp_path).generate_text(
            DISPUTE_PROMPT,
            dispute_variables("hola"),
            language=Language.ES,
            max_output_tokens=10,
            temperature=0.0,
            call_context=CONTEXT,
        )


async def test_a_text_cassette_must_hold_a_string(tmp_path: Path) -> None:
    _fixture(tmp_path, kind="text", output_model=None)

    with pytest.raises(CassetteMismatchError, match="must hold a string"):
        await _player(tmp_path).generate_text(
            DISPUTE_PROMPT,
            dispute_variables("hola"),
            language=Language.ES,
            max_output_tokens=10,
            temperature=0.0,
            call_context=CONTEXT,
        )


async def test_an_outdated_structured_output_is_invalid_output(tmp_path: Path) -> None:
    _fixture(tmp_path, output={"intent_candidates": []})

    with pytest.raises(LlmInvalidOutputError, match="no longer fits"):
        await _extract(_player(tmp_path), "hola")


def test_configuration_errors(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="model id"):
        CassetteLLM(tmp_path, model_id="", redactor=Redactor(), clock=FixedClock(NOW))
    with pytest.raises(ConfigurationError, match="inner client"):
        CassetteLLM(tmp_path, model_id=MODEL, redactor=Redactor(), clock=FixedClock(NOW), mode=CassetteMode.RECORD)
