"""Chaos: failing tools, a partial write, a model registry that fails at startup (L3), the risk estimator failing
mid-conversation, and a credit catalog that cannot load. Each ends safely, in es and pt, with a complete record."""

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from bank_agent.adapters.reliability.monitor import DegradationMonitor
from bank_agent.application.grounding.draft import GroundingContext, ResponseDraft, Violation, ViolationKind
from bank_agent.application.grounding.verifier import GroundingVerifier
from bank_agent.application.reliability.ladder import LadderFlags
from bank_agent.bootstrap.models import ModelFallbacks
from bank_agent.bootstrap.policy import build_policy
from bank_agent.bootstrap.retrieval import build_grounding
from bank_agent.bootstrap.settings import PolicySettings, RetrievalSettings
from bank_agent.domain.actions import ToolFailureMode, ToolName
from bank_agent.domain.degradation import ComponentState, DegradationLevel
from bank_agent.domain.eligibility import CreditRiskFeatures, EligibilityOutcome, ReviewReason, RiskEstimate
from bank_agent.domain.errors import RiskEstimatorUnavailableError
from bank_agent.domain.execution_record import ToolCallStatus
from bank_agent.domain.intelligence import ResolvedArtifact
from bank_agent.domain.workflow import Outcome
from bank_agent.policy.lexicon import approval_terms
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_agent.testing.telemetry import RecordingTelemetry
from bank_agent_scenarios import CO, MX, NOW, PT
from bank_agent_workflow_support import Backend
from bank_agent_workflows import POLICY_DIR, Harness, build_harness, shared_policy

HANDED_OFF = {MX: "persona del equipo", CO: "persona del equipo", PT: "pessoa da equipe"}
BALANCE = {MX: "¿Cuál es mi saldo?", PT: "Qual é o meu saldo?"}


async def _complete(harness: Harness, customer: str, turn_id: str) -> None:
    """The turn left a full execution record: state, outcome, latency, policy version, and consistent totals."""
    record = await harness.record(harness.session(customer), turn_id)
    assert record.state_after
    assert record.policy_pack_version.startswith("pack-")
    assert record.latency.total_ms >= 0
    assert [call.sequence for call in record.tool_calls] == list(range(1, len(record.tool_calls) + 1))


@pytest.mark.parametrize("mode", [ToolFailureMode.TIMEOUT, ToolFailureMode.TRANSIENT_ERROR,
                                  ToolFailureMode.PERMANENT_ERROR])  # fmt: skip
@pytest.mark.parametrize("customer", [MX, PT])
async def test_a_failing_read_tool_hands_off_after_the_retry_budget_without_an_answer(
    backend: Backend, mode: ToolFailureMode, customer: str
) -> None:
    harness = build_harness(backend.uow_factory, backend.session_store,
                            failures={ToolName.LIST_MY_BALANCES: mode})  # fmt: skip
    reply = await harness.say(BALANCE[customer], harness.session(customer))
    assert (reply.state, reply.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert HANDED_OFF[customer] in reply.response.text
    assert reply.response.balances == ()
    record = await harness.record(harness.session(customer), reply.turn_id)
    (failed,) = [call for call in record.tool_calls if call.tool is ToolName.LIST_MY_BALANCES]
    expected_attempts = 1 if mode is ToolFailureMode.PERMANENT_ERROR else 3
    assert (failed.status, failed.attempts) == (ToolCallStatus.FAILED, expected_attempts)
    assert reply.response.escalation is not None
    handoff = (await harness.handoff(harness.session(customer), reply.response.escalation.handoff_id)).handoff
    assert handoff.escalation_reason.code.value == "tool_failure"
    await _complete(harness, customer, reply.turn_id)


@pytest.mark.parametrize(
    ("customer", "opening", "decline", "confirm", "done_word"),
    [(MX, "No reconozco un cargo de 1250 pesos en FIXTURE MARKET del 15 de junio", "no", "sí", "registramos"),
     (PT, "Não reconheço uma compra de 88 pesos na PADARIA BOA", "não", "sim", "registramos")],
)  # fmt: skip
async def test_a_partial_write_is_caught_by_the_read_back_in_es_and_pt(
    backend: Backend, customer: str, opening: str, decline: str, confirm: str, done_word: str
) -> None:
    failures = {ToolName.CREATE_DISPUTE_CASE: ToolFailureMode.PARTIAL_WRITE}
    harness = build_harness(backend.uow_factory, backend.session_store, failures=failures)
    session = harness.session(customer, step_up=True)
    first = await harness.say(opening, session)
    await harness.say(decline, session, first.conversation_id)
    reply = await harness.say(confirm, session, first.conversation_id)
    assert (reply.state, reply.outcome) == ("ESCALATED", Outcome.ESCALATED)
    assert done_word not in reply.response.text
    assert HANDED_OFF[customer] in reply.response.text
    assert all(status.status.value != "verified" for status in reply.response.action_statuses)
    record = await harness.record(session, reply.turn_id)
    write = next(call for call in record.tool_calls if call.tool is ToolName.CREATE_DISPUTE_CASE)
    assert write.verification is not None
    assert write.verification.verified is False
    await _complete(harness, customer, reply.turn_id)


class UnreachableRegistry:
    """A ``ModelRegistry`` whose storage cannot be read (a failed mount, a permission error)."""

    def resolve(self, name: str, version_or_alias: str) -> ResolvedArtifact:
        raise PermissionError("the model store is not readable")


async def test_a_registry_failure_at_startup_serves_the_baselines_as_l3_in_es_and_pt(backend: Backend) -> None:
    fallbacks = ModelFallbacks(router_threshold=0.75)
    monitor = DegradationMonitor(
        clock=FixedClock(NOW), telemetry=RecordingTelemetry(), flags=LadderFlags(),
        models_on_baseline=fallbacks.served_baseline,
    )  # fmt: skip
    harness = build_harness(
        backend.uow_factory, backend.session_store, model_registry=UnreachableRegistry(), fallbacks=fallbacks,
        degradation=monitor, router="tfidf@champion", resolver="lgbm@champion", risk_selection="logreg@champion",
    )  # fmt: skip
    assert fallbacks.served_baseline == ["risk_estimator", "router", "resolver"]
    assert monitor.current().level is DegradationLevel.MODEL_BASELINES

    balance = await harness.say(BALANCE[MX], harness.session(MX))
    assert balance.outcome is Outcome.RESOLVED
    record = await harness.record(harness.session(MX), balance.turn_id)
    assert "router:keyword@1" in {str(model) for model in record.models}
    assert "degradation_l3" in record.safety_interventions

    for customer, text, unavailable in (
        (CO, "Quiero saber si califico para un préstamo personal de 10 millones de pesos a 36 meses",
         "La estimación de riesgo no está disponible."),
        (PT, "Sou elegível para um cartão de crédito com limite de 30 mil pesos?",
         "A estimativa de risco não está disponível."),
    ):  # fmt: skip
        session = harness.session(customer, step_up=True)
        reply = await harness.say(text, session)
        assert reply.response.eligibility is not None
        assert reply.response.eligibility.outcome is EligibilityOutcome.REVIEW_REQUIRED
        assert unavailable in reply.response.text
        assert approval_terms(reply.response.text) == ()
        credit_record = await harness.record(session, reply.turn_id)
        assert credit_record.risk_estimates == ()
        (assessment,) = credit_record.eligibility_assessments
        assert ReviewReason.RISK_ESTIMATE_UNAVAILABLE in assessment.review_reasons


class EstimatorThatFails:
    """A ``RiskEstimator`` that breaks while conversations are running (never a default estimate)."""

    def __init__(self) -> None:
        self.calls = 0

    def estimate(self, features: CreditRiskFeatures) -> RiskEstimate:
        self.calls += 1
        raise RiskEstimatorUnavailableError("fixture: the estimator stopped mid-conversation")


@pytest.mark.parametrize(
    ("customer", "opening", "question", "unavailable"),
    [(CO, "¿Qué condiciones tiene el préstamo personal?",
      "Quiero saber si califico para un préstamo personal de 10 millones de pesos a 36 meses",
      "La estimación de riesgo no está disponible."),
     (PT, "Quais produtos de crédito vocês têm?", "Sou elegível para um cartão de crédito com limite de 30 mil pesos?",
      "A estimativa de risco não está disponível.")],
)  # fmt: skip
async def test_the_risk_estimator_failing_mid_conversation_sends_eligibility_to_review(
    backend: Backend, customer: str, opening: str, question: str, unavailable: str
) -> None:
    estimator = EstimatorThatFails()
    harness = build_harness(backend.uow_factory, backend.session_store, risk_estimator=estimator)
    session = harness.session(customer, step_up=True)
    first = await harness.say(opening, session)
    assert first.response.eligibility is None
    reply = await harness.say(question, session, first.conversation_id)
    assert estimator.calls == 1
    assert reply.response.eligibility is not None
    assert reply.response.eligibility.outcome is EligibilityOutcome.REVIEW_REQUIRED
    assert unavailable in reply.response.text
    assert approval_terms(reply.response.text) == ()
    record = await harness.record(session, reply.turn_id)
    assert record.risk_estimates == ()
    assert "risk_estimate_unavailable" in record.safety_interventions
    await _complete(harness, customer, reply.turn_id)


def _pack_without_catalog(tmp_path: Path) -> Path:
    copied = tmp_path / "policies"
    shutil.copytree(POLICY_DIR, copied)
    for entry in (copied / "credit").glob("*.yaml"):
        entry.unlink()
    return copied


async def test_a_credit_catalog_that_cannot_load_disables_credit_only(backend: Backend, tmp_path: Path) -> None:
    policy = build_policy(
        PolicySettings(dir=_pack_without_catalog(tmp_path)), clock=FixedClock(NOW), ids=SequentialIdGenerator(),
        catalog_fallback=True,
    )  # fmt: skip
    assert not policy.credit_catalog_available
    grounding = build_grounding(RetrievalSettings(), policy.repository)
    monitor = DegradationMonitor(clock=FixedClock(NOW), telemetry=RecordingTelemetry(), flags=LadderFlags(),
                                 credit_catalog=ComponentState.UNAVAILABLE)  # fmt: skip
    harness = build_harness(backend.uow_factory, backend.session_store, pack=(policy, grounding), degradation=monitor)
    assert monitor.current().reasons == ("credit_catalog_unavailable",)

    for customer, text, refusal in (
        (CO, "¿Qué condiciones tiene el préstamo personal?", "Eso no lo puedo hacer aquí"),
        (PT, "Quais produtos de crédito vocês têm?", "Isso eu não consigo fazer aqui"),
    ):
        reply = await harness.say(text, harness.session(customer))
        assert refusal in reply.response.text
        assert reply.response.credit_products == ()
        assert reply.workflow is not None
        assert reply.workflow.id != "credit"
        await _complete(harness, customer, reply.turn_id)

    for customer in (MX, PT):
        balance = await harness.say(BALANCE[customer], harness.session(customer))
        assert balance.outcome is Outcome.RESOLVED
        assert balance.workflow is not None
        assert balance.workflow.id == "account_inquiry"
    card = await harness.say("Perdí mi tarjeta, bloquéala por favor", harness.session(CO))
    assert card.state == "CONFIRM_BLOCK"


class ApprovalEverywhere(GroundingVerifier):
    """A verifier that finds approval wording in every draft: stands in for a template bug the detectors must stop."""

    def verify(self, draft: ResponseDraft, context: GroundingContext) -> tuple[Violation, ...]:
        return (Violation(kind=ViolationKind.APPROVAL_WORDING, detail="fixture: approval wording"),)


@pytest.mark.parametrize(
    ("customer", "blocked"),
    [(MX, "No puedo darte esa respuesta en este momento"), (PT, "Não posso dar essa resposta no momento")],
)
async def test_an_unsafe_template_is_blocked_before_it_is_sent(backend: Backend, customer: str, blocked: str) -> None:
    policy, grounding = shared_policy()
    flagged = replace(grounding, verifier=ApprovalEverywhere(policy.repository))
    harness = build_harness(backend.uow_factory, backend.session_store, pack=(policy, flagged))
    reply = await harness.say(BALANCE[customer], harness.session(customer))
    assert reply.response.text.startswith(blocked)
    assert reply.response.template_id == "common.unsafe_blocked"
    assert reply.response.balances == ()
    record = await harness.record(harness.session(customer), reply.turn_id)
    assert "unsafe_output_blocked" in record.safety_interventions
    assert "approval_wording" in record.grounding.violations
    await _complete(harness, customer, reply.turn_id)
