"""The live verifier accepts Langfuse v4 metadata and rejects a broken privacy or call link."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "verify_e2e_tracing.py"
TRACE_ID = "a" * 32
CALL_ID = "b" * 16
SCHEMA_HASH = "c" * 64


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_e2e_tracing", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_e2e_tracing"] = module
    spec.loader.exec_module(module)
    return module


verifier = _load()


def _generation() -> dict[str, Any]:
    return {
        "traceId": TRACE_ID,
        "type": "GENERATION",
        "model": "openai/gpt-5-mini",
        "input": None,
        "output": None,
        "user_id": "",
        "usage_details": {"input": 7, "output": 3, "total": 10},
        "cost_details": {"total": 0.000012},
        "metadata": {
            "call_id": CALL_ID,
            "trace_id": TRACE_ID,
            "conversation_id": "conv-fixture",
            "correlation_id": "turn-fixture",
            "prompt_id": "extract_account_inquiry_slots",
            "prompt_version": 1,
            "schema_id": "AccountSlots",
            "schema_version": SCHEMA_HASH[:12],
            "schema_hash": SCHEMA_HASH,
            "provider_returned_model_id": "gpt-5-mini",
            "status": "success",
            "latency_ms": 42,
            "attributes.gen_ai.provider.name": "openai",
        },
    }


def _record() -> dict[str, Any]:
    return {
        "conversation_id": "conv-fixture",
        "turn_id": "turn-fixture",
        "calls": {
            CALL_ID: {
                "prompt": "extract_account_inquiry_slots@1",
                "model_id": "openai/gpt-5-mini",
                "input_tokens": 7,
                "output_tokens": 3,
                "latency_ms": 42,
                "cost_usd": "0.000012",
            }
        },
    }


def _verify(monkeypatch: pytest.MonkeyPatch, generation: dict[str, Any]) -> None:
    class FakeClient:
        def __init__(self, **_: object) -> None:
            observations = SimpleNamespace(get_many=lambda **__: SimpleNamespace(data=[generation]))
            self.api = SimpleNamespace(observations=observations)

        def shutdown(self) -> None:
            pass

    monkeypatch.setitem(sys.modules, "langfuse", SimpleNamespace(Langfuse=FakeClient))
    fixture_key = "fixture"
    config = verifier.Config(
        model="openai/gpt-5-mini",
        database_url=None,
        public_key="fixture",
        secret_key=fixture_key,
        host="http://langfuse.fixture",
        persona_id="persona-fixture",
        message="fixture",
    )
    verifier.verify_langfuse(config, TRACE_ID, _record())


def test_v4_generation_matches_the_record_and_empty_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _verify(monkeypatch, _generation())


@pytest.mark.parametrize(("field", "value"), [("input", "private customer text"), ("user_id", "customer-123")])
def test_rejects_content_or_customer_identifier(monkeypatch: pytest.MonkeyPatch, field: str, value: str) -> None:
    generation = _generation()
    generation[field] = value
    with pytest.raises(verifier.VerificationError):
        _verify(monkeypatch, generation)


def test_rejects_a_model_call_id_without_a_postgres_match(monkeypatch: pytest.MonkeyPatch) -> None:
    generation = _generation()
    generation["metadata"]["call_id"] = "d" * 16
    with pytest.raises(verifier.VerificationError, match="model_call_id"):
        _verify(monkeypatch, generation)
