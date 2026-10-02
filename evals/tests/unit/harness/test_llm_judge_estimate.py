"""The run's language model modes and cassette coverage, the judge and its agreement, the estimate, and the
Portuguese proposal helper."""

from decimal import Decimal
from pathlib import Path

import pytest
from bank_evals_support import graded, result, scenario, turn

from bank_agent.adapters.llm.cassette import CassetteLLM, CassetteMode
from bank_agent.adapters.llm.prices import PriceTable
from bank_agent.adapters.llm.redaction import Redactor
from bank_agent.bootstrap.settings import LLMSettings
from bank_agent.domain.errors import ConfigurationError, LlmProviderRejectedError
from bank_agent.domain.intelligence import LlmCallContext, PromptRef
from bank_agent.domain.locale import Language
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.fake_llm import FakeLLM, ScriptedError, ScriptedResponse
from bank_evals.judge import agreement, cohen_kappa, judge, stratified_sample
from bank_evals.prompts.outputs import JudgeRating
from bank_evals.runner.estimate import estimate_run
from bank_evals.runner.llm import EVALUATION_UNREDACTED_VARIABLE_KEYS, build_run_llm, model_label
from bank_evals.runner.wiring import prompt_registry
from bank_evals.scenarios.translate import propose_portuguese
from bank_evals.systems.base import LlmCallView
from bank_evals.world.model import NOW

JUDGE = PromptRef(prompt_id="judge_transcript", version=1)
RATING = {"language_correct": True, "tone": 5, "clarity": 4, "politeness": 5, "language_quality": 3}
VARIABLES = {"expected_language": "es-MX", "transcript": "x"}


async def test_off_refuses_every_call_and_labels_the_run_without_a_model() -> None:
    llm = build_run_llm(LLMSettings(), prompt_registry(), "off")
    assert (llm.available, llm.model_label) == (False, "none")
    with pytest.raises(LlmProviderRejectedError):
        await llm.client.generate_structured(
            JUDGE,
            VARIABLES,
            JudgeRating,
            language=Language.ES,
            max_output_tokens=50,
            temperature=0.0,
            call_context=LlmCallContext(),
        )


async def test_replay_serves_recorded_cassettes_and_counts_the_misses(tmp_path: Path) -> None:
    model = "ollama/qwen2.5:7b-instruct"
    inner = FakeLLM()
    inner.script(JUDGE, ScriptedResponse(output=RATING))
    recorder = CassetteLLM(
        tmp_path, model_id=model, redactor=Redactor(), clock=FixedClock(NOW), mode=CassetteMode.RECORD, inner=inner
    )
    await recorder.generate_structured(
        JUDGE,
        VARIABLES,
        JudgeRating,
        language=Language.ES,
        max_output_tokens=50,
        temperature=0.0,
        call_context=LlmCallContext(),
    )
    llm = build_run_llm(LLMSettings(primary_model=model), prompt_registry(), "replay", cassette_dir=tmp_path)
    hit = await llm.client.generate_structured(
        JUDGE,
        VARIABLES,
        JudgeRating,
        language=Language.ES,
        max_output_tokens=50,
        temperature=0.0,
        call_context=LlmCallContext(),
    )
    assert hit.value.tone == 5
    with pytest.raises(LlmProviderRejectedError):
        await llm.client.generate_text(
            PromptRef(prompt_id="translate_to_portuguese", version=1),
            {"spanish_text": "hola"},
            language=Language.PT,
            max_output_tokens=50,
            temperature=0.0,
            call_context=LlmCallContext(),
        )
    assert llm.misses.total == 1
    assert model_label(LLMSettings(primary_model=model), "replay") == f"{model} (cassettes)"


def test_replay_and_inject_need_a_model_or_a_client() -> None:
    with pytest.raises(ConfigurationError, match="LLM_PRIMARY_MODEL"):
        build_run_llm(LLMSettings(), prompt_registry(), "replay")
    with pytest.raises(ConfigurationError, match="inject"):
        build_run_llm(LLMSettings(), prompt_registry(), "inject")


def test_evaluation_redactor_keeps_synthetic_simulator_figures() -> None:
    redactor = Redactor(EVALUATION_UNREDACTED_VARIABLE_KEYS)
    variables = {
        "goal": "Pedir 15000000 pesos",
        "instructions": "Di 15000000",
        "known_facts": "amount: 15000000",
        "customer_message": "Mi documento es 15000000",
    }
    redacted = redactor.redact_variables(variables)
    assert redacted["known_facts"] == "amount: 15000000"
    assert redacted["customer_message"] == "Mi documento es [DOCUMENT]"


async def test_the_judge_rates_a_stratified_sample_and_agreement_waits_for_humans() -> None:
    results = [
        result(scenario(id=f"s-{i:03d}", language=lang, dialect=dialect), None, system)
        for i, (lang, dialect, system) in enumerate(
            [("es", "es-MX", "p"), ("pt", "pt-BR", "p"), ("es", "es-CO", "b1"), ("pt", "pt-BR", "b1")]
        )
    ]
    for item in results:
        item.grade = None
    assert stratified_sample(results, 2) == []
    for item in results:
        item.grade = graded(scenario(), [turn()])
    sample = stratified_sample(results, 3)
    assert len(sample) == 3
    assert len({(r.system, r.language) for r in sample}) == 3
    fake = FakeLLM()
    fake.script(JUDGE, ScriptedResponse(output=RATING), ScriptedError(LlmProviderRejectedError))
    rated = await judge(fake, sample[0])
    assert rated is not None
    assert rated.tone == 5
    assert await judge(fake, sample[1]) is None
    rows = [{"judge": RATING, "human": None}]
    assert agreement(rows)["status"] == "pending"
    human = {**RATING, "language_quality": 5}
    computed = agreement([{"judge": RATING, "human": human}, {"judge": RATING, "human": RATING}])
    assert computed["status"] == "computed"
    assert computed["tone"]["percent_agreement"] == 1.0
    assert computed["language_quality"]["percent_agreement"] == 0.5


def test_cohens_kappa_matches_a_hand_computed_value() -> None:
    pairs = [(True, True)] * 20 + [(True, False)] * 5 + [(False, True)] * 10 + [(False, False)] * 15
    assert cohen_kappa(pairs) == pytest.approx(0.4)
    assert cohen_kappa([]) is None
    assert cohen_kappa([(True, True)]) is None


def test_the_estimate_projects_calls_wall_clock_and_cost() -> None:
    call = LlmCallView(prompt="p", model="m", status="ok", input_tokens=1000, output_tokens=100, latency_ms=4000)
    measured = []
    for system in ("p", "b1"):
        item = result(scenario(), None, system)
        item.transcript.turns = [turn(llm_calls=[call, call])]
        measured.append(item)
    prices = PriceTable.from_yaml(LLMSettings().prices_file)
    out = estimate_run(
        measured, scenarios=332, simulated=68, judge_sample=100, prices=prices, price_model="openai/gpt-5-mini"
    )
    assert out["calls_per_case"] == {"p": 2.0, "b1": 2.0}
    assert out["total_calls"] == 332 * 2 * 2 + 300
    assert out["projected_wall_clock_hours"] == pytest.approx(out["total_calls"] * 4 / 3600, abs=0.01)
    assert Decimal(out["projected_cost_usd"]) > 0


async def test_portuguese_proposals_are_always_pending_review() -> None:
    fake = FakeLLM()
    prompt = PromptRef(prompt_id="translate_to_portuguese", version=1)
    fake.script(prompt, ScriptedResponse(output="Qual é o meu saldo?"), ScriptedError(LlmProviderRejectedError))
    proposals = await propose_portuguese(fake, ["¿Cuál es mi saldo?", "Hola"])
    assert [p["pt"] for p in proposals] == ["Qual é o meu saldo?", None]
    assert {p["review_status"] for p in proposals} == {"pending_review"}
