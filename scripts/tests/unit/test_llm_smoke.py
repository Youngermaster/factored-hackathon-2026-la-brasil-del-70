"""The opt-in LLM smoke script, without a provider: case loading, the reachability checks, and the report."""

import importlib.util
import json
import sys
import urllib.error
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from bank_agent.bootstrap.settings import LLMSettings
from bank_agent.domain.errors import LlmTimeoutError
from bank_agent.domain.llm_outputs import DisputeSlotExtraction

SCRIPT = Path(__file__).resolve().parents[2] / "llm_smoke.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("llm_smoke", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["llm_smoke"] = module
    spec.loader.exec_module(module)
    return module


smoke = _load()
OLLAMA = LLMSettings(provider="litellm", primary_model="ollama/qwen2.5:7b-instruct", api_base="http://localhost:11434")


def _tags(*names: str) -> Any:
    return lambda url, timeout: json.dumps({"models": [{"name": name} for name in names]}).encode()


def test_every_fixture_case_is_loaded_in_both_languages_for_all_four_workflows() -> None:
    cases = smoke.load_cases()
    assert len(cases) == 32
    assert {case.language.value for case in cases} == {"es", "pt"}
    assert {case.labels["workflow"] for case in cases} == {"dispute", "account_inquiry", "card_support", "credit"}
    assert smoke.output_model("DisputeSlotExtraction") is DisputeSlotExtraction
    with pytest.raises(smoke.SmokeSetupError):
        smoke.output_model("NotAModel")


def test_the_provider_must_be_a_configured_live_one() -> None:
    with pytest.raises(smoke.SmokeSetupError, match="LLM_PROVIDER=litellm"):
        smoke.check_provider(LLMSettings())
    hosted = smoke.check_provider(LLMSettings(provider="litellm", primary_model="openai/gpt-5-mini"))
    assert "hosted" in hosted


def test_ollama_must_be_reachable_and_have_the_model_pulled() -> None:
    def unreachable(url: str, timeout: float) -> bytes:
        raise urllib.error.URLError("connection refused")

    with pytest.raises(smoke.SmokeSetupError, match="ollama serve"):
        smoke.check_provider(OLLAMA, fetch=unreachable)
    with pytest.raises(smoke.SmokeSetupError, match=r"ollama pull qwen2\.5:7b-instruct"):
        smoke.check_provider(OLLAMA, fetch=_tags("llama3:8b"))
    assert smoke.check_provider(OLLAMA, fetch=_tags("qwen2.5:7b-instruct")) == (
        "ollama/qwen2.5:7b-instruct at http://localhost:11434"
    )
    with pytest.raises(smoke.SmokeSetupError, match="http"):
        smoke.check_provider(OLLAMA.model_copy(update={"api_base": "file:///etc"}), fetch=_tags())


class TimingOutClient:
    async def generate_structured(self, *args: object, **kwargs: object) -> object:
        raise LlmTimeoutError("slow")

    async def generate_text(self, *args: object, **kwargs: object) -> object:
        raise LlmTimeoutError("slow")


async def test_a_failing_case_is_reported_with_the_error_code() -> None:
    case = smoke.load_cases()[0]
    result = await smoke.run_case(TimingOutClient(), case, 1)
    assert (result.passed, result.detail) == (False, "llm_timeout")


def test_the_report_lists_each_case_and_the_pass_rate_and_latency() -> None:
    results = [
        smoke.CaseResult("extract_dispute_slots@1", "dispute", "normal", "es", True, 1200, "ok"),
        smoke.CaseResult("phrase_response@1", "credit", "normal", "pt", False, 3000, "llm_invalid_output"),
    ]
    report = smoke.summarize(results)
    assert "fail: llm_invalid_output" in report
    assert "passed 1 of 2" in report
    assert "local development measurement" in report


def test_main_exits_2_when_no_live_provider_is_configured(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_PRIMARY_MODEL", raising=False)
    assert smoke.main(["--no-env-file"]) == 2
    assert "LLM_PROVIDER=litellm" in capsys.readouterr().err
