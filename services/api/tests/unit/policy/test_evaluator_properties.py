"""Property tests of the policy kernel invariants (Hypothesis)."""

from datetime import timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from bank_agent.domain.access import AuthLevel
from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.transaction import TransactionStatus
from bank_agent.domain.trust import TrustEventKind
from bank_agent.domain.workflow import Intent
from bank_agent.policy.evaluator import evaluate
from bank_agent.policy.facts import DisputeFacts, EscalationSignals, EvaluationRequest, PolicyFacts, PrivacySignals
from bank_agent_policy import DATA_AS_OF, facts, fixture_pack, request, snapshot, transaction_facts, trust

PACK = fixture_pack()
AUTOMATIC = frozenset({DecisionKind.ALLOW, DecisionKind.REQUIRE_CONFIRMATION})

escalations = st.builds(
    EscalationSignals,
    human_requested=st.booleans(),
    legal_or_regulator_mention=st.booleans(),
    distress_signal=st.booleans(),
    clarification_attempts=st.integers(0, 4),
    tool_failures_after_retries=st.integers(0, 2),
    verification_mismatch=st.booleans(),
    prior_complaints_in_lookback=st.integers(0, 5),
)
privacy = st.builds(PrivacySignals, other_customer_reference=st.booleans(), third_party_request=st.booleans())
transactions = st.one_of(
    st.none(),
    st.builds(
        lambda days, status, owned, disputed, cents: transaction_facts(
            occurred_on=DATA_AS_OF - timedelta(days=days),
            status=status,
            owned_by_session_customer=owned,
            has_open_dispute=disputed,
            amount=Money.of(f"{cents}.00", Currency.MXN),
        ),
        st.integers(-2, 200),
        st.sampled_from(TransactionStatus),
        st.booleans(),
        st.booleans(),
        st.integers(1, 30000),
    ),
)
disputes = st.builds(
    DisputeFacts,
    transaction=transactions,
    reason=st.one_of(st.none(), st.sampled_from(DisputeReason)),
    disputed_amount=st.one_of(st.none(), st.integers(1, 30000).map(lambda n: Money.of(f"{n}.00", Currency.MXN))),
)
policy_facts = st.builds(
    lambda intent, esc, prv, dispute: facts(intent=intent, escalation=esc, privacy=prv, dispute=dispute),
    st.one_of(st.none(), st.sampled_from(Intent)),
    escalations,
    privacy,
    disputes,
)
TIERS = ((), (TrustEventKind.INJECTION_DETECTED,), (TrustEventKind.CROSS_CUSTOMER_PROBE,))


def _escalating(value: PolicyFacts) -> bool:
    signals = value.escalation
    return (
        signals.human_requested
        or signals.legal_or_regulator_mention
        or signals.distress_signal
        or signals.clarification_attempts >= 2
        or signals.tool_failures_after_retries > 0
        or signals.verification_mismatch
        or signals.prior_complaints_in_lookback >= 3
    )


@settings(max_examples=150, deadline=None)
@given(policy_facts, st.sampled_from([AuthLevel.NONE, AuthLevel.IDENTIFIED]), st.booleans())
def test_insufficient_auth_always_denies_or_asks_for_step_up(
    value: PolicyFacts, level: AuthLevel, expired: bool
) -> None:
    decision = evaluate(request(facts_=value, session=snapshot(level, expired=expired)), PACK)
    assert decision.kind in {DecisionKind.DENY, DecisionKind.REQUIRE_STEP_UP}


@settings(max_examples=150, deadline=None)
@given(policy_facts, st.booleans())
def test_a_higher_risk_tier_never_relaxes_a_requirement(value: PolicyFacts, step_up: bool) -> None:
    decisions = [
        evaluate(request(facts_=value, session=snapshot(step_up=step_up), trust_=trust(*kinds)), PACK)
        for kinds in TIERS
    ]
    automatic = [decision.kind in AUTOMATIC for decision in decisions]
    assert automatic == sorted(automatic, reverse=True)
    levels = [
        AuthLevel(str(next(r for r in d.rule_results if r.rule_id == "AUTH.required_level").params["required_level"]))
        for d in decisions
    ]
    assert [level.rank for level in levels] == sorted(level.rank for level in levels)


@settings(max_examples=150, deadline=None)
@given(policy_facts)
def test_any_escalation_trigger_prevents_automatic_resolution(value: PolicyFacts) -> None:
    decision = evaluate(request(facts_=value), PACK)
    if _escalating(value):
        assert decision.kind not in AUTOMATIC


@settings(max_examples=100, deadline=None)
@given(policy_facts, st.sampled_from(TIERS))
def test_identical_inputs_give_identical_decisions(value: PolicyFacts, kinds: tuple[TrustEventKind, ...]) -> None:
    first: EvaluationRequest = request(facts_=value, trust_=trust(*kinds))
    second = EvaluationRequest.model_validate(first.model_dump())
    assert evaluate(first, PACK) == evaluate(second, PACK)
