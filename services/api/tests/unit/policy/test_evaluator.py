"""The evaluator over the in-memory fixture pack: rule selection, order, and precedence."""

from datetime import date
from typing import Any

import pytest

from bank_agent.domain.access import AuthLevel
from bank_agent.domain.actions import ActionKind
from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.errors import PolicyBindingMissingError
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.product import ProductStatus
from bank_agent.domain.workflow import Intent, WorkflowId
from bank_agent.policy.evaluator import FAMILY_ORDER, evaluate, rules_for
from bank_agent.policy.facts import (
    CardFacts,
    DisputeFacts,
    EscalationSignals,
    PolicyFacts,
    PrivacySignals,
    TransactionFacts,
)
from bank_agent.policy.pack import PolicyPack
from bank_agent_policy import action, facts, fixture_pack, request, snapshot, transaction_facts


@pytest.fixture(scope="module")
def pack() -> PolicyPack:
    return fixture_pack()


def dispute_facts(transaction: TransactionFacts | None = None, **overrides: Any) -> PolicyFacts:
    amount = Money.of("1500.00", Currency.MXN)
    dispute = DisputeFacts(
        transaction=transaction or transaction_facts(), reason=DisputeReason.UNRECOGNIZED, disputed_amount=amount
    )
    return facts(intent=Intent.DISPUTE_NEW, dispute=dispute, **overrides)


def test_rules_come_from_the_bound_clauses_in_family_order(pack: PolicyPack) -> None:
    rule_ids = rules_for(request(), pack)
    families = [rule_id.split(".")[0] for rule_id in rule_ids]
    assert families == sorted(families, key=FAMILY_ORDER.index)
    assert "DSP.within_window" in rule_ids
    assert not any(rule_id.startswith(("CRD.", "ELG.")) for rule_id in rule_ids)


def test_a_clean_dispute_is_allowed_and_names_every_rule_and_clause(pack: PolicyPack) -> None:
    decision = evaluate(request(facts_=dispute_facts()), pack)
    assert decision.kind is DecisionKind.ALLOW
    assert decision.policy_pack_version == pack.version
    assert {ref.clause_id for ref in decision.clause_refs} >= {"DSP-MX-1", "DSP-ALL-1", "AUTH-ALL-1"}
    assert all(result.passed for result in decision.rule_results)


def test_an_unknown_state_is_a_binding_error(pack: PolicyPack) -> None:
    with pytest.raises(PolicyBindingMissingError):
        evaluate(request(state="NOWHERE"), pack)


def test_missing_facts_clarify(pack: PolicyPack) -> None:
    decision = evaluate(request(facts_=facts(intent=Intent.DISPUTE_NEW)), pack)
    assert decision.kind is DecisionKind.CLARIFY
    assert "DSP.required_fields_present" in decision.decisive_rule_ids


def test_authentication_failures_dominate_escalation_and_refusal(pack: PolicyPack) -> None:
    loud = dispute_facts(
        escalation=EscalationSignals(human_requested=True), privacy=PrivacySignals(third_party_request=True)
    )
    decision = evaluate(request(facts_=loud, session=snapshot(AuthLevel.IDENTIFIED)), pack)
    assert decision.kind is DecisionKind.DENY
    assert set(decision.decisive_rule_ids) <= {"AUTH.required_level", "AUTH.session_valid", "AUTH.step_up_valid"}


def test_refusal_beats_escalation_and_escalation_beats_denial(pack: PolicyPack) -> None:
    both = dispute_facts(
        escalation=EscalationSignals(legal_or_regulator_mention=True), privacy=PrivacySignals(third_party_request=True)
    )
    assert evaluate(request(facts_=both), pack).kind is DecisionKind.REFUSE
    old = transaction_facts(occurred_on=date(2025, 6, 1))
    closed = dispute_facts(old, escalation=EscalationSignals(human_requested=True))
    escalated = evaluate(request(facts_=closed), pack)
    assert escalated.kind is DecisionKind.ESCALATE
    assert escalated.decisive_rule_ids == ("ESC.human_requested",)


def test_an_action_needs_step_up_then_confirmation_then_it_is_allowed(pack: PolicyPack) -> None:
    card = CardFacts(owned_by_session_customer=True, is_card=True, status=ProductStatus.ACTIVE)
    card_facts = facts(intent=Intent.CARD_BLOCK, card=card)
    unconfirmed = action(ActionKind.BLOCK_CARD, "CONFIRM_BLOCK")
    first = evaluate(request(WorkflowId.CARD_SUPPORT, "CONFIRM_BLOCK", facts_=card_facts, action_=unconfirmed), pack)
    assert first.kind is DecisionKind.REQUIRE_STEP_UP
    stepped = snapshot(step_up=True)
    second = evaluate(
        request(WorkflowId.CARD_SUPPORT, "CONFIRM_BLOCK", facts_=card_facts, action_=unconfirmed, session=stepped), pack
    )
    assert second.kind is DecisionKind.REQUIRE_CONFIRMATION
    assert second.action is ActionKind.BLOCK_CARD
    confirmed = action(ActionKind.BLOCK_CARD, "EXECUTE_BLOCK", confirmed=True)
    third = evaluate(
        request(WorkflowId.CARD_SUPPORT, "EXECUTE_BLOCK", facts_=card_facts, action_=confirmed, session=stepped), pack
    )
    assert third.kind is DecisionKind.ALLOW


def test_an_action_outside_its_states_is_denied(pack: PolicyPack) -> None:
    card = CardFacts(owned_by_session_customer=True, is_card=True, status=ProductStatus.ACTIVE)
    blocked = action(ActionKind.BLOCK_CARD, "IDENTIFY_CARD", confirmed=True)
    decision = evaluate(
        request(
            WorkflowId.CARD_SUPPORT,
            "IDENTIFY_CARD",
            facts_=facts(intent=Intent.CARD_BLOCK, card=card),
            action_=blocked,
            session=snapshot(step_up=True),
        ),
        pack,
    )
    assert decision.kind is DecisionKind.DENY
    assert decision.decisive_rule_ids == ("SCOPE.action_allowed_in_state",)


def test_the_window_uses_the_data_as_of_date_not_the_evaluation_instant(pack: PolicyPack) -> None:
    decision = evaluate(request(facts_=dispute_facts()), pack)
    window = next(result for result in decision.rule_results if result.rule_id == "DSP.within_window")
    assert window.params["days_since_transaction"] == 16
