from decimal import Decimal

import pytest
from pydantic import ValidationError

from bank_agent.domain.errors import InvalidProductStateError
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.product import ProductStatus, ProductType
from bank_agent.domain.transaction import Transaction
from bank_agent_builders import complaint, customer, product, transaction


def test_customer_carries_only_the_first_name_as_personal_data() -> None:
    fields = set(type(customer()).model_fields)
    assert fields == {"customer_id", "country", "segment", "status", "first_name"}


def test_blocks_an_active_card() -> None:
    card = product()
    assert card.is_card
    assert card.blocked().status is ProductStatus.BLOCKED


def test_blocking_a_blocked_card_is_a_no_op() -> None:
    blocked = product(status=ProductStatus.BLOCKED)
    assert blocked.blocked() is blocked


@pytest.mark.parametrize(
    ("product_type", "status"),
    [
        (ProductType.SAVINGS_ACCOUNT, ProductStatus.ACTIVE),
        (ProductType.DEBIT_CARD, ProductStatus.CLOSED),
        (ProductType.CREDIT_CARD, ProductStatus.SUSPENDED),
    ],
)
def test_refuses_to_block_non_cards_and_inactive_cards(product_type: ProductType, status: ProductStatus) -> None:
    with pytest.raises(InvalidProductStateError):
        product(product_type=product_type, status=status).blocked()


def test_fraud_context_is_internal_and_hidden_from_repr() -> None:
    txn = transaction()
    assert "fraud" not in repr(txn)
    assert txn.fraud_score == Decimal("12.5")
    schema = Transaction.model_json_schema()
    assert schema["properties"]["fraud"]["x-internal"] is True


def test_rejects_a_usd_amount_in_another_currency() -> None:
    fields = transaction().model_dump()
    fields["amount_usd"] = Money.of("10", Currency.MXN)
    with pytest.raises(ValidationError):
        Transaction.model_validate(fields)


def test_accepts_a_foreign_purchase_location() -> None:
    assert transaction(location_country="US").location_country == "US"


def test_rejects_naive_datetimes() -> None:
    fields = complaint().model_dump()
    fields["created_at"] = fields["created_at"].replace(tzinfo=None)
    with pytest.raises(ValidationError):
        type(complaint()).model_validate(fields)
