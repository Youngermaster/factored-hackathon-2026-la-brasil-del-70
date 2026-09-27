"""AUTH, PRV, and SCOPE rules, called directly with a rule context."""

import pytest

from bank_agent.domain.access import AuthLevel, Role
from bank_agent.domain.actions import ActionKind
from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.trust import TrustEventKind
from bank_agent.domain.workflow import Intent, WorkflowId
from bank_agent.policy.facts import PrivacySignals
from bank_agent.policy.rules import CONVERSATION_RULES, RuleContext
from bank_agent_policy import FIXTURE_MATRIX, action, context, facts, request, snapshot, trust

AUTH_PARAMS = {"elevated_risk_required_level": "step_up", "step_up_window_minutes": 5}
SCOPE_PARAMS = {"supported_workflows": ["account_inquiry", "card_support", "dispute", "credit"]}


def run(rule_id: str, ctx: RuleContext) -> tuple[bool, str, DecisionKind | None]:
    result = CONVERSATION_RULES[rule_id].run(ctx, ())
    return result.passed, result.reason_code, result.effect


def test_a_missing_session_passes_only_when_the_state_needs_no_authentication() -> None:
    anonymous = request(session=None)
    anonymous = anonymous.model_copy(update={"session": None})
    assert run("AUTH.session_valid", context(request_=anonymous, state_auth=AuthLevel.NONE))[:2] == (
        True,
        "no_session_required",
    )
    failed = CONVERSATION_RULES["AUTH.session_valid"].run(context(request_=anonymous), ())
    assert (failed.passed, failed.effect, failed.missing_facts) == (False, DecisionKind.DENY, ("session",))


def test_expired_and_staff_sessions_are_denied() -> None:
    assert run("AUTH.session_valid", context(request_=request(session=snapshot(expired=True))))[1] == "session_expired"
    staff = request(session=snapshot(role=Role.AGENT))
    assert run("AUTH.session_valid", context(request_=staff))[1] == "not_a_customer_session"
    assert run("AUTH.session_valid", context())[:2] == (True, "session_valid")


@pytest.mark.parametrize(
    ("level", "state_auth", "expected"),
    [
        (AuthLevel.OTP_VERIFIED, AuthLevel.OTP_VERIFIED, (True, "auth_level_sufficient", None)),
        (AuthLevel.IDENTIFIED, AuthLevel.OTP_VERIFIED, (False, "auth_level_insufficient", DecisionKind.DENY)),
        (AuthLevel.NONE, AuthLevel.NONE, (True, "auth_level_sufficient", None)),
    ],
)
def test_required_level_compares_the_session_with_the_state(
    level: AuthLevel, state_auth: AuthLevel, expected: tuple[bool, str, DecisionKind | None]
) -> None:
    ctx = context(AUTH_PARAMS, request_=request(session=snapshot(level)), state_auth=state_auth)
    assert run("AUTH.required_level", ctx) == expected


def test_an_elevated_risk_tier_raises_the_level_to_step_up() -> None:
    elevated = request(trust_=trust(TrustEventKind.INJECTION_DETECTED))
    assert run("AUTH.required_level", context(AUTH_PARAMS, request_=elevated)) == (
        False,
        "step_up_required",
        DecisionKind.REQUIRE_STEP_UP,
    )
    stepped = request(session=snapshot(step_up=True), trust_=trust(TrustEventKind.INJECTION_DETECTED))
    assert run("AUTH.required_level", context(AUTH_PARAMS, request_=stepped))[0] is True


def test_an_elevated_tier_does_not_raise_states_that_need_no_authentication() -> None:
    elevated = request(session=None, trust_=trust(TrustEventKind.INJECTION_DETECTED))
    ctx = context(AUTH_PARAMS, request_=elevated.model_copy(update={"session": None}), state_auth=AuthLevel.NONE)
    assert run("AUTH.required_level", ctx)[0] is True


def test_step_up_rule_applies_only_to_actions_that_need_it() -> None:
    requirement = FIXTURE_MATRIX[ActionKind.BLOCK_CARD]
    assert run("AUTH.step_up_valid", context(AUTH_PARAMS))[1] == "step_up_not_required"
    ctx = context(AUTH_PARAMS, requirement=requirement)
    assert run("AUTH.step_up_valid", ctx) == (False, "step_up_required", DecisionKind.REQUIRE_STEP_UP)
    stepped = context(AUTH_PARAMS, request_=request(session=snapshot(step_up=True)), requirement=requirement)
    assert run("AUTH.step_up_valid", stepped)[:2] == (True, "step_up_valid")
    weak = context(AUTH_PARAMS, request_=request(session=snapshot(AuthLevel.IDENTIFIED)), requirement=requirement)
    assert run("AUTH.step_up_valid", weak) == (False, "step_up_needs_verified_session", DecisionKind.DENY)


@pytest.mark.parametrize(
    ("signals", "rule_id", "reason"),
    [
        (PrivacySignals(other_customer_reference=True), "PRV.no_cross_customer_access", "cross_customer_access"),
        (PrivacySignals(third_party_request=True), "PRV.no_third_party_disclosure", "third_party_request"),
    ],
)
def test_privacy_signals_refuse(signals: PrivacySignals, rule_id: str, reason: str) -> None:
    ctx = context(request_=request(facts_=facts(privacy=signals)))
    assert run(rule_id, ctx) == (False, reason, DecisionKind.REFUSE)
    assert run(rule_id, context())[0] is True


def test_a_workflow_left_out_of_the_supported_list_abstains() -> None:
    reduced = {"supported_workflows": ["account_inquiry", "card_support", "dispute"]}
    ctx = context(reduced, request_=request(WorkflowId.CREDIT, "PRODUCT_DETAIL"))
    assert run("SCOPE.workflow_supported", ctx) == (False, "workflow_not_supported", DecisionKind.ABSTAIN)
    assert run("SCOPE.workflow_supported", context(SCOPE_PARAMS))[0] is True


@pytest.mark.parametrize(
    ("intent", "expected"),
    [
        (None, (False, "intent_unknown", DecisionKind.CLARIFY)),
        (Intent.UNSUPPORTED, (False, "intent_unsupported", DecisionKind.ABSTAIN)),
        (Intent.HUMAN_REQUEST, (True, "intent_cross_workflow", None)),
        (Intent.DISPUTE_STATUS, (True, "intent_supported", None)),
        (Intent.BALANCE_INQUIRY, (False, "intent_owned_by_other_workflow", DecisionKind.CLARIFY)),
    ],
)
def test_supported_intent(intent: Intent | None, expected: tuple[bool, str, DecisionKind | None]) -> None:
    assert run("SCOPE.supported_intent", context(request_=request(facts_=facts(intent=intent)))) == expected


def test_actions_must_belong_to_the_workflow_and_the_state() -> None:
    assert run("SCOPE.action_allowed_in_state", context())[1] == "no_action"
    block = FIXTURE_MATRIX[ActionKind.BLOCK_CARD]
    in_credit = request(WorkflowId.CREDIT, "SUBMIT_APPLICATION", action_=action(ActionKind.BLOCK_CARD, "X"))
    assert run("SCOPE.action_allowed_in_state", context(request_=in_credit, requirement=block))[1] == (
        "action_not_allowed_in_workflow"
    )
    wrong_state = request(WorkflowId.DISPUTE, "COLLECT_DETAILS", action_=action(ActionKind.BLOCK_CARD, "X"))
    assert run("SCOPE.action_allowed_in_state", context(request_=wrong_state, requirement=block))[1] == (
        "action_not_allowed_in_state"
    )
    right = request(WorkflowId.DISPUTE, "EXECUTE_BLOCK", action_=action(ActionKind.BLOCK_CARD, "EXECUTE_BLOCK"))
    assert run("SCOPE.action_allowed_in_state", context(request_=right, requirement=block))[:2] == (
        True,
        "action_allowed",
    )
