"""Router dispatch as a table: dispatch, switches, shared intents, out of scope, and uncertain predictions."""

import pytest

from bank_agent.application.engine.registry import WorkflowRegistry
from bank_agent.application.engine.router import Route, RouteKind, dispatch
from bank_agent.domain.intelligence import IntentPrediction, IntentScore
from bank_agent.domain.workflow import Intent, WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG
from bank_agent.testing.models import FAKE_ROUTER

DSP, CRD = WorkflowId.DISPUTE, WorkflowId.CARD_SUPPORT
REGISTRY = WorkflowRegistry(name="t", definitions={}, enabled=frozenset({DSP, CRD}), catalog=WORKFLOW_CATALOG)


def predicted(intent: Intent, confidence: float = 0.9, *others: tuple[Intent, float]) -> IntentPrediction:
    candidates = (IntentScore(intent=intent, score=confidence), *(IntentScore(intent=i, score=s) for i, s in others))
    return IntentPrediction(
        intent=intent, confidence=confidence, candidates=candidates, below_threshold=confidence < 0.6, model=FAKE_ROUTER
    )


@pytest.mark.parametrize(
    ("intent", "current", "mid_flow", "expected"),
    [
        (Intent.DISPUTE_NEW, None, False, Route(RouteKind.START, DSP)),
        (Intent.CARD_STATUS, DSP, False, Route(RouteKind.SWITCH, CRD)),
        (Intent.DISPUTE_NEW, CRD, True, Route(RouteKind.CONFIRM_SWITCH, DSP)),
        (Intent.DISPUTE_STATUS, DSP, True, Route(RouteKind.CONTINUE, DSP)),
        (Intent.INFORMATIONAL, DSP, True, Route(RouteKind.INFORMATIONAL)),
        (Intent.HUMAN_REQUEST, None, False, Route(RouteKind.HUMAN)),
        (Intent.GREETING_OR_OTHER, None, False, Route(RouteKind.GREETING)),
        (Intent.UNSUPPORTED, DSP, False, Route(RouteKind.OUT_OF_SCOPE)),
        (Intent.BALANCE_INQUIRY, None, False, Route(RouteKind.OUT_OF_SCOPE)),
        (Intent.CREDIT_PRODUCT_INFO, CRD, True, Route(RouteKind.OUT_OF_SCOPE)),
    ],
)
def test_dispatch_table(intent: Intent, current: WorkflowId | None, mid_flow: bool, expected: Route) -> None:
    assert dispatch(predicted(intent), REGISTRY, current=current, mid_flow=mid_flow) == expected


def test_an_uncertain_prediction_offers_the_two_most_likely_enabled_workflows() -> None:
    prediction = predicted(Intent.CARD_STATUS, 0.5, (Intent.DISPUTE_NEW, 0.45))
    assert dispatch(prediction, REGISTRY, current=None, mid_flow=False) == Route(
        RouteKind.CLARIFY_WORKFLOW, options=(CRD, DSP)
    )
    unmatched = predicted(Intent.GREETING_OR_OTHER, 0.2)
    assert dispatch(unmatched, REGISTRY, current=None, mid_flow=False).options == (CRD, DSP)


def test_a_matched_greeting_is_a_greeting_even_below_the_threshold() -> None:
    assert dispatch(predicted(Intent.GREETING_OR_OTHER, 0.55), REGISTRY, current=None, mid_flow=False).kind is (
        RouteKind.GREETING
    )


def test_a_single_enabled_workflow_is_started_or_continued_when_uncertain() -> None:
    single = WorkflowRegistry(name="t", definitions={}, enabled=frozenset({DSP}), catalog=WORKFLOW_CATALOG)
    uncertain = predicted(Intent.DISPUTE_NEW, 0.5)
    assert dispatch(uncertain, single, current=None, mid_flow=False) == Route(RouteKind.START, DSP)
    assert dispatch(uncertain, single, current=DSP, mid_flow=False) == Route(RouteKind.CONTINUE, DSP)
    empty = WorkflowRegistry(name="t", definitions={}, enabled=frozenset(), catalog=WORKFLOW_CATALOG)
    assert dispatch(uncertain, empty, current=None, mid_flow=False).kind is RouteKind.GREETING
