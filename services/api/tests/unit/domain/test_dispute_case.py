from datetime import timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from bank_agent.domain.dispute import ALLOWED_TRANSITIONS, TERMINAL_STATUSES, DisputeCase, DisputeReason, DisputeStatus
from bank_agent.domain.errors import InvalidCaseTransitionError
from bank_agent.domain.identifiers import CaseId, IdempotencyKey
from bank_agent.domain.money import Currency, Money
from bank_agent_builders import T0, dispute_case, transaction

LEGAL = [(source, target) for source, targets in ALLOWED_TRANSITIONS.items() for target in targets]
ILLEGAL = [
    (source, target)
    for source in DisputeStatus
    for target in DisputeStatus
    if target not in ALLOWED_TRANSITIONS[source]
]


def _case_in(status: DisputeStatus) -> DisputeCase:
    case = dispute_case()
    path = {
        DisputeStatus.OPENED: [],
        DisputeStatus.IN_REVIEW: [DisputeStatus.IN_REVIEW],
        DisputeStatus.ESCALATED: [DisputeStatus.ESCALATED],
        DisputeStatus.RESOLVED: [DisputeStatus.IN_REVIEW, DisputeStatus.RESOLVED],
        DisputeStatus.REJECTED: [DisputeStatus.REJECTED],
    }[status]
    for step in path:
        case = case.transition_to(step, at=T0, reason_code="setup")
    return case


def test_opening_copies_ownership_from_the_transaction() -> None:
    txn = transaction(customer_id="CUS-B-0002", product_id="PRD-B-CARD")
    case = dispute_case(txn=txn)
    assert case.customer_id == "CUS-B-0002"
    assert case.product_id == "PRD-B-CARD"
    assert case.disputed_amount == txn.amount
    assert case.status is DisputeStatus.OPENED
    assert case.is_open


def test_rejects_a_disputed_amount_in_another_currency() -> None:
    with pytest.raises(ValueError, match="transaction currency"):
        DisputeCase.open(
            case_id=CaseId("case-1"),
            transaction=transaction(),
            reason=DisputeReason.WRONG_AMOUNT,
            opened_at=T0,
            sla_due_at=T0,
            idempotency_key=IdempotencyKey("idem-key-fixture-0009"),
            disputed_amount=Money.of("1", Currency.USD),
        )


@pytest.mark.parametrize(("source", "target"), LEGAL)
def test_allows_every_listed_transition(source: DisputeStatus, target: DisputeStatus) -> None:
    moved = _case_in(source).transition_to(target, at=T0 + timedelta(hours=1), reason_code="review")
    assert moved.status is target
    assert moved.status_history[-1].from_status is source
    assert moved.updated_at == T0 + timedelta(hours=1)


@pytest.mark.parametrize(("source", "target"), ILLEGAL)
def test_rejects_every_unlisted_transition(source: DisputeStatus, target: DisputeStatus) -> None:
    with pytest.raises(InvalidCaseTransitionError):
        _case_in(source).transition_to(target, at=T0, reason_code="review")


def test_has_no_shortcut_from_opened_to_resolved() -> None:
    assert DisputeStatus.RESOLVED not in ALLOWED_TRANSITIONS[DisputeStatus.OPENED]


def test_rejects_a_change_dated_before_the_last_update() -> None:
    case = dispute_case().transition_to(DisputeStatus.IN_REVIEW, at=T0 + timedelta(hours=2), reason_code="review")
    with pytest.raises(InvalidCaseTransitionError):
        case.transition_to(DisputeStatus.RESOLVED, at=T0 + timedelta(hours=1), reason_code="late")


def test_rejects_an_sla_before_opening() -> None:
    case = dispute_case()
    with pytest.raises(ValueError, match="cannot precede"):
        case.evolve(sla_due_at=T0 - timedelta(days=1))


@given(st.lists(st.sampled_from(list(DisputeStatus)), max_size=12))
def test_random_transitions_follow_the_table_and_never_leave_terminal_states(targets: list[DisputeStatus]) -> None:
    case = dispute_case()
    for target in targets:
        allowed = target in ALLOWED_TRANSITIONS[case.status]
        was_terminal = case.status in TERMINAL_STATUSES
        try:
            case = case.transition_to(target, at=T0, reason_code="random")
        except InvalidCaseTransitionError:
            assert not allowed
        else:
            assert allowed
            assert not was_terminal
