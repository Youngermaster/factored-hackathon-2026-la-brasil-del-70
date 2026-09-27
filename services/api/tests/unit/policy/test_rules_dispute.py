"""DSP and CRE rules: window day N passes and N+1 fails, amounts at the limit, every status, missing facts."""

from datetime import timedelta
from typing import Any

import pytest

from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.transaction import TransactionStatus
from bank_agent.domain.workflow import Intent, WorkflowId
from bank_agent.policy.facts import CreditFacts, DisputeFacts
from bank_agent.policy.rules import CONVERSATION_RULES, RuleContext
from bank_agent_credit import catalog_products
from bank_agent_policy import DATA_AS_OF, FIXTURE_CLAUSES, context, facts, request, transaction_facts

DSP_PARAMS: dict[str, Any] = {
    **FIXTURE_CLAUSES["DSP-ALL-1"][0],
    **FIXTURE_CLAUSES["DSP-MX-1"][0],
    **FIXTURE_CLAUSES["DSP-MX-3"][0],
}


def run(rule_id: str, ctx: RuleContext) -> tuple[bool, str, DecisionKind | None, tuple[str, ...]]:
    result = CONVERSATION_RULES[rule_id].run(ctx, ())
    return result.passed, result.reason_code, result.effect, result.missing_facts


def dispute(**fields: Any) -> RuleContext:
    facts_ = facts(intent=Intent.DISPUTE_NEW, dispute=DisputeFacts.model_validate(fields))
    return context(DSP_PARAMS, request_=request(facts_=facts_))


def with_transaction(reason: DisputeReason | None = DisputeReason.UNRECOGNIZED, **fields: Any) -> RuleContext:
    amount = fields.pop("disputed_amount", None)
    return dispute(transaction=transaction_facts(**fields), reason=reason, disputed_amount=amount)


TRANSACTION_RULES = (
    "DSP.transaction_owned_by_session_customer",
    "DSP.within_window",
    "DSP.status_eligible",
    "DSP.not_already_disputed",
)


@pytest.mark.parametrize("rule_id", TRANSACTION_RULES)
def test_a_missing_transaction_asks_for_it(rule_id: str) -> None:
    assert run(rule_id, dispute())[1:] == ("transaction_unknown", DecisionKind.CLARIFY, ("transaction",))


def test_another_customers_transaction_is_refused() -> None:
    assert run("DSP.transaction_owned_by_session_customer", with_transaction(owned_by_session_customer=False))[2] is (
        DecisionKind.REFUSE
    )


@pytest.mark.parametrize(("days", "passed"), [(0, True), (89, True), (90, True), (91, False)])
def test_the_window_counts_days_to_the_data_as_of_date(days: int, passed: bool) -> None:
    passed_, reason, effect, _ = run("DSP.within_window", with_transaction(occurred_on=DATA_AS_OF - timedelta(days)))
    assert passed_ is passed
    assert (reason, effect) == (
        ("within_dispute_window", None) if passed else ("dispute_window_closed", DecisionKind.DENY)
    )


def test_a_transaction_after_the_data_as_of_date_escalates() -> None:
    later = with_transaction(occurred_on=DATA_AS_OF + timedelta(days=1))
    assert run("DSP.within_window", later)[1:3] == ("transaction_date_after_as_of", DecisionKind.ESCALATE)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (TransactionStatus.APPROVED, (True, "status_eligible", None)),
        (TransactionStatus.PENDING, (False, "transaction_pending", DecisionKind.ABSTAIN)),
        (TransactionStatus.DECLINED, (False, "transaction_status_not_eligible", DecisionKind.DENY)),
        (TransactionStatus.REVERSED, (False, "transaction_status_not_eligible", DecisionKind.DENY)),
    ],
)
def test_every_status(status: TransactionStatus, expected: tuple[object, ...]) -> None:
    assert run("DSP.status_eligible", with_transaction(status=status))[:3] == expected


def test_an_open_dispute_blocks_a_second_one() -> None:
    assert run("DSP.not_already_disputed", with_transaction(has_open_dispute=True))[1] == "already_disputed"
    assert run("DSP.not_already_disputed", with_transaction())[0]


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (None, (False, "reason_unknown", DecisionKind.CLARIFY)),
        (DisputeReason.OTHER, (False, "reason_needs_human", DecisionKind.ESCALATE)),
        (DisputeReason.DUPLICATE, (True, "reason_supported", None)),
    ],
)
def test_reason_taxonomy(reason: DisputeReason | None, expected: tuple[object, ...]) -> None:
    assert run("DSP.reason_supported", with_transaction(reason=reason))[:3] == expected


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (Money.of("9999.99", Currency.MXN), (True, "amount_within_auto_limit", None)),
        (Money.of("10000.00", Currency.MXN), (True, "amount_within_auto_limit", None)),
        (Money.of("10000.01", Currency.MXN), (False, "amount_above_auto_limit", DecisionKind.ESCALATE)),
        (Money.of("100.00", Currency.USD), (False, "amount_not_comparable", DecisionKind.ESCALATE)),
    ],
)
def test_amount_limit_is_inclusive(amount: Money, expected: tuple[object, ...]) -> None:
    ctx = dispute(transaction=transaction_facts(amount=amount), disputed_amount=amount)
    assert run("DSP.amount_within_auto_limit", ctx)[:3] == expected


def test_the_transaction_amount_stands_in_for_a_missing_disputed_amount() -> None:
    assert run("DSP.amount_within_auto_limit", with_transaction())[0]
    assert run("DSP.amount_within_auto_limit", dispute())[1:] == (
        "amount_unknown",
        DecisionKind.CLARIFY,
        ("disputed_amount",),
    )


def test_required_fields() -> None:
    assert run("DSP.required_fields_present", dispute())[3] == ("transaction", "reason", "disputed_amount")
    too_much = with_transaction(disputed_amount=Money.of("1500.01", Currency.MXN))
    assert run("DSP.required_fields_present", too_much)[1] == "disputed_amount_exceeds_transaction"
    zero = with_transaction(disputed_amount=Money.of("0", Currency.MXN))
    assert run("DSP.required_fields_present", zero)[1] == "disputed_amount_not_positive"
    exact = with_transaction(disputed_amount=Money.of("1500.00", Currency.MXN))
    assert run("DSP.required_fields_present", exact)[0]


def credit(country: Country = Country.MX, **fields: Any) -> RuleContext:
    facts_ = facts(country, intent=Intent.CREDIT_PRODUCT_INFO, credit=CreditFacts.model_validate(fields))
    return context(request_=request(WorkflowId.CREDIT, "PRODUCT_DETAIL", facts_=facts_))


def test_credit_product_rules() -> None:
    loan = next(p for p in catalog_products() if p.product_code == "MX-PL-FIXTURE")
    assert run("CRE.product_in_catalog", credit())[1:] == ("product_unknown", DecisionKind.CLARIFY, ("credit_product",))
    assert run("CRE.product_in_catalog", credit(requested_product_code="MX-NOPE"))[1] == "product_not_in_catalog"
    assert run("CRE.product_in_catalog", credit(product=loan))[0]
    assert run("CRE.offered_in_jurisdiction", credit(Country.CO, product=loan))[2] is DecisionKind.DENY
    assert run("CRE.offered_in_jurisdiction", credit(product=loan))[0]
    assert run("CRE.offered_in_jurisdiction", credit())[1] == "product_unknown"
    assert run("CRE.disclaimer_present", credit())[1] == "disclaimer_missing"
    assert run("CRE.disclaimer_present", credit(disclaimer_included=True))[0]


def test_an_open_case_past_its_sla_escalates() -> None:
    assert run("DSP.case_within_sla", dispute(case_sla_breached=True))[1:3] == (
        "case_sla_breached",
        DecisionKind.ESCALATE,
    )
    assert run("DSP.case_within_sla", dispute())[:2] == (True, "case_within_sla")
