"""Named persona criteria: SQL predicates over the gold serving views, evaluated in DuckDB.

Each predicate refers to the candidate customer as ``c``. ``$snapshot`` is the dataset snapshot date; "recent"
means within 30 days before it. Two transfers are similar when their amounts differ by at most 5 percent within
a week (amounts in the data are continuous, so equal amounts are rare). The borderline band (640 to 660)
brackets 650, the value the synthetic eligibility threshold is expected to take; phase 06 owns the real
parameter and may move the band.
"""

RECENT_DAYS = 30
BORDERLINE_LOW, BORDERLINE_HIGH = 640, 660

_PRODUCT = "EXISTS (SELECT 1 FROM products_serving p WHERE p.customer_id = c.customer_id AND {condition})"
_TRANSACTION = (
    "EXISTS (SELECT 1 FROM transactions_serving t JOIN products_serving p ON p.product_id = t.product_id "
    "AND p.customer_id = t.customer_id WHERE t.customer_id = c.customer_id AND {condition})"
)
_PROFILE = "EXISTS (SELECT 1 FROM credit_profiles_serving f WHERE f.customer_id = c.customer_id AND {condition})"

CRITERIA: dict[str, str] = {
    "checking_and_savings_with_balances": " AND ".join(
        _PRODUCT.format(
            condition=f"p.product_type = '{kind}' AND p.product_status = 'active' AND p.current_balance IS NOT NULL"
        )
        for kind in ("checking_account", "savings_account")
    ),
    "pending_and_reversed_payment": " AND ".join(
        _TRANSACTION.format(condition=f"t.transaction_type = 'payment' AND t.transaction_status = '{status}'")
        for status in ("pending", "reversed")
    ),
    "two_similar_transfers": (
        "EXISTS (SELECT 1 FROM transactions_serving a JOIN transactions_serving b ON a.customer_id = b.customer_id "
        "AND a.transaction_id < b.transaction_id AND a.currency = b.currency "
        "AND abs(a.amount - b.amount) <= a.amount * 0.05 "
        "AND abs(date_diff('day', a.transaction_at, b.transaction_at)) <= 7 "
        "WHERE a.customer_id = c.customer_id AND a.transaction_type = 'transfer' AND b.transaction_type = 'transfer')"
    ),
    "two_active_cards": (
        "(SELECT count(*) FROM products_serving p WHERE p.customer_id = c.customer_id AND p.is_card "
        "AND p.product_status = 'active') >= 2"
    ),
    "card_with_declined_purchase": _TRANSACTION.format(
        condition="p.is_card AND t.transaction_type = 'purchase' AND t.transaction_status = 'declined'"
    ),
    "expired_card": _PRODUCT.format(condition="p.is_card AND p.expiration_date < $snapshot"),
    "blocked_card": _PRODUCT.format(condition="p.is_card AND p.product_status = 'blocked'"),
    "card_with_recent_purchase": _TRANSACTION.format(
        condition="p.is_card AND p.product_status = 'active' AND t.transaction_type = 'purchase' "
        f"AND t.transaction_status = 'approved' AND t.merchant_name IS NOT NULL "
        f"AND t.transaction_at >= $snapshot - INTERVAL {RECENT_DAYS} DAY"
    ),
    "repeat_complainer": (
        "(SELECT count(*) FROM complaints_serving k WHERE k.customer_id = c.customer_id "
        "AND k.created_at >= $snapshot - INTERVAL 365 DAY) >= 3"
    ),
    "similar_purchases": (
        "EXISTS (SELECT t.merchant_name FROM transactions_serving t WHERE t.customer_id = c.customer_id "
        "AND t.transaction_type = 'purchase' AND t.merchant_name IS NOT NULL GROUP BY t.merchant_name "
        "HAVING count(*) >= 3 AND date_diff('day', min(t.transaction_at), max(t.transaction_at)) <= 30)"
    ),
    "complete_credit_profile": _PROFILE.format(
        condition="f.credit_score >= 700 AND f.estimated_monthly_income IS NOT NULL AND f.tenure_months IS NOT NULL "
        "AND f.utilization IS NOT NULL AND coalesce(f.max_days_past_due, 0) = 0"
    ),
    "credit_profile_without_income": _PROFILE.format(
        condition="f.estimated_monthly_income IS NULL AND f.credit_score IS NOT NULL"
    ),
    "borderline_credit_score": _PROFILE.format(
        condition=f"f.credit_score BETWEEN {BORDERLINE_LOW} AND {BORDERLINE_HIGH} "
        "AND f.estimated_monthly_income IS NOT NULL AND coalesce(f.max_days_past_due, 0) = 0"
    ),
    "credit_days_past_due": _PROFILE.format(condition="f.max_days_past_due > 0"),
}
