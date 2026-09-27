"""Rows of the core banking tables (customers, products, transactions, complaints, credit profiles)."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from bank_agent.domain.customer import Customer, CustomerSegment, CustomerStatus
from bank_agent.domain.identifiers import CustomerId, ProductId, TransactionId
from bank_agent.domain.locale import Country
from bank_agent.domain.masking import MaskedNumber
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.product import Product, ProductStatus, ProductType
from bank_agent.domain.transaction import (
    FraudContext,
    Transaction,
    TransactionCategory,
    TransactionChannel,
    TransactionStatus,
    TransactionType,
)

Row = Mapping[str, Any]


def money_or_none(amount: Decimal | None, currency: str | None) -> Money | None:
    if amount is None or currency is None:
        return None
    return Money.of(amount, Currency(currency))


def amount_of(money: Money | None) -> Decimal | None:
    return None if money is None else money.amount


def currency_of(money: Money | None) -> str | None:
    return None if money is None else money.currency.value


def customer_from_row(row: Row) -> Customer:
    return Customer(
        customer_id=CustomerId(row["customer_id"]),
        country=Country(row["country"]),
        segment=CustomerSegment(row["segment"]),
        status=CustomerStatus(row["status"]),
        first_name=row["first_name"],
    )


def customer_to_row(customer: Customer) -> dict[str, Any]:
    return {
        "customer_id": customer.customer_id,
        "country": customer.country.value,
        "segment": customer.segment.value,
        "status": customer.status.value,
        "first_name": customer.first_name,
    }


def product_from_row(row: Row) -> Product:
    currency = row["currency"]
    return Product(
        product_id=ProductId(row["product_id"]),
        customer_id=CustomerId(row["customer_id"]),
        product_type=ProductType(row["product_type"]),
        status=ProductStatus(row["status"]),
        masked_number=MaskedNumber(last4=row["number_last4"]),
        currency=Currency(currency),
        current_balance=money_or_none(row["current_balance"], currency),
        credit_limit=money_or_none(row["credit_limit"], currency),
        annual_interest_rate=row["annual_interest_rate"],
        opened_on=row["opened_on"],
        expires_on=row["expires_on"],
        balance_as_of=row["balance_as_of"],
        days_past_due=row["days_past_due"],
    )


def product_to_row(product: Product) -> dict[str, Any]:
    return {
        "product_id": product.product_id,
        "customer_id": product.customer_id,
        "product_type": product.product_type.value,
        "status": product.status.value,
        "number_last4": product.masked_number.last4,
        "currency": product.currency.value,
        "current_balance": amount_of(product.current_balance),
        "credit_limit": amount_of(product.credit_limit),
        "annual_interest_rate": product.annual_interest_rate,
        "opened_on": product.opened_on,
        "expires_on": product.expires_on,
        "balance_as_of": product.balance_as_of,
        "days_past_due": product.days_past_due,
    }


def transaction_from_row(row: Row) -> Transaction:
    category = row["category"]
    return Transaction(
        transaction_id=TransactionId(row["transaction_id"]),
        customer_id=CustomerId(row["customer_id"]),
        product_id=ProductId(row["product_id"]),
        occurred_at=row["occurred_at"],
        transaction_type=TransactionType(row["transaction_type"]),
        category=TransactionCategory(category) if category is not None else None,
        amount=Money.of(row["amount"], Currency(row["currency"])),
        amount_usd=money_or_none(row["amount_usd"], Currency.USD.value),
        channel=TransactionChannel(row["channel"]),
        status=TransactionStatus(row["status"]),
        merchant_name=row["merchant_name"],
        merchant_category=row["merchant_category"],
        location_country=row["location_country"],
        location_city=row["location_city"],
        fraud=FraudContext(label=row["fraud_label"], score=row["fraud_score"]),
    )


def transaction_to_row(txn: Transaction) -> dict[str, Any]:
    return {
        "transaction_id": txn.transaction_id,
        "customer_id": txn.customer_id,
        "product_id": txn.product_id,
        "occurred_at": txn.occurred_at,
        "transaction_type": txn.transaction_type.value,
        "category": txn.category.value if txn.category is not None else None,
        "amount": txn.amount.amount,
        "currency": txn.amount.currency.value,
        "amount_usd": amount_of(txn.amount_usd),
        "channel": txn.channel.value,
        "status": txn.status.value,
        "merchant_name": txn.merchant_name,
        "merchant_category": txn.merchant_category,
        "location_country": txn.location_country,
        "location_city": txn.location_city,
        "fraud_label": txn.fraud.label,
        "fraud_score": txn.fraud.score,
    }
