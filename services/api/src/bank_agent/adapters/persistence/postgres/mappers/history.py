"""Rows of the read-only history tables: historical complaints and credit profiles."""

from typing import Any

from bank_agent.adapters.persistence.postgres.mappers.accounts import Row, amount_of, currency_of, money_or_none
from bank_agent.domain.complaint import ComplaintCaseType, ComplaintChannel, HistoricalComplaint, Priority
from bank_agent.domain.credit import CreditProfile
from bank_agent.domain.identifiers import ComplaintId, CustomerId, ProductId


def complaint_from_row(row: Row) -> HistoricalComplaint:
    affected = row["affected_product_id"]
    return HistoricalComplaint(
        complaint_id=ComplaintId(row["complaint_id"]),
        customer_id=CustomerId(row["customer_id"]),
        created_at=row["created_at"],
        case_type=ComplaintCaseType(row["case_type"]),
        category=row["category"],
        subcategory=row["subcategory"],
        reception_channel=ComplaintChannel(row["reception_channel"]),
        affected_product_id=ProductId(affected) if affected else None,
        claimed_amount=money_or_none(row["claimed_amount"], row["currency"]),
        priority=Priority(row["priority"]),
    )


def complaint_to_row(complaint: HistoricalComplaint) -> dict[str, Any]:
    return {
        "complaint_id": complaint.complaint_id,
        "customer_id": complaint.customer_id,
        "created_at": complaint.created_at,
        "case_type": complaint.case_type.value,
        "category": complaint.category,
        "subcategory": complaint.subcategory,
        "reception_channel": complaint.reception_channel.value,
        "affected_product_id": complaint.affected_product_id,
        "claimed_amount": amount_of(complaint.claimed_amount),
        "currency": currency_of(complaint.claimed_amount),
        "priority": complaint.priority.value,
    }


def credit_profile_from_row(row: Row) -> CreditProfile:
    return CreditProfile(
        customer_id=CustomerId(row["customer_id"]),
        credit_score=row["credit_score"],
        estimated_monthly_income=money_or_none(row["estimated_monthly_income"], row["income_currency"]),
        tenure_months=row["tenure_months"],
        credit_product_count=row["credit_product_count"],
        max_days_past_due=row["max_days_past_due"],
        total_credit_limit=money_or_none(row["total_credit_limit"], row["total_credit_limit_currency"]),
        utilization=row["utilization"],
        as_of=row["as_of"],
    )


def credit_profile_to_row(profile: CreditProfile) -> dict[str, Any]:
    return {
        "customer_id": profile.customer_id,
        "credit_score": profile.credit_score,
        "estimated_monthly_income": amount_of(profile.estimated_monthly_income),
        "income_currency": currency_of(profile.estimated_monthly_income),
        "tenure_months": profile.tenure_months,
        "credit_product_count": profile.credit_product_count,
        "max_days_past_due": profile.max_days_past_due,
        "total_credit_limit": amount_of(profile.total_credit_limit),
        "total_credit_limit_currency": currency_of(profile.total_credit_limit),
        "utilization": profile.utilization,
        "as_of": profile.as_of,
    }
