"""Warehouse reads for the analysis. Every query reads the silver and gold relations built by dbt; nothing
here writes to the warehouse (the connection is read-only)."""

from collections.abc import Mapping
from dataclasses import dataclass

import duckdb
import pandas as pd

from bank_data.analysis.config import SCENARIOS, WorkflowMapping

COUNTRY_UTC_OFFSET_HOURS: Mapping[str, int] = {"MX": -6, "CO": -5, "AR": -3}
"""Fixed offsets for local hours of day: none of the three countries observed daylight saving time in the
data period (2023 to 2026). Timestamps are UTC (the phase 03 reading)."""


def _mapping_frame(mapping: WorkflowMapping, source: str) -> pd.DataFrame:
    rows = [
        {
            "value": row.value,
            "subcategory": row.subcategory,
            "sub_intent": row.sub_intent,
            **{f"workflow_{scenario}": row.workflow_for(scenario) for scenario in SCENARIOS},  # type: ignore[arg-type]
        }
        for row in mapping.for_source(source)
    ]
    columns = ["value", "subcategory", "sub_intent", *(f"workflow_{scenario}" for scenario in SCENARIOS)]
    return pd.DataFrame(rows, columns=columns).astype("string")


def register_mapping(connection: duckdb.DuckDBPyConnection, mapping: WorkflowMapping) -> None:
    """Expose the mapping to SQL as ``map_contact_reason``, ``map_reason_category``, ``map_complaint``."""
    for source, name in (
        ("contact_reason", "map_contact_reason"),
        ("reason_category", "map_reason_category"),
        ("complaint_category", "map_complaint"),
    ):
        connection.register(name, _mapping_frame(mapping, source))


def interactions(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Every interaction with its customer's country and segment and its workflow in each scenario (null
    when the contact reason has no mapping row)."""
    return connection.execute(
        """
        select
            i.interaction_id, i.interaction_date, i.process_date, i.customer_id, i.channel, i.interaction_type,
            i.contact_reason, i.reason_category, i.duration_seconds, i.wait_time_seconds, i.was_resolved,
            i.was_escalated, i.requires_followup, i.customer_detected_accent,
            c.country, c.segment, m.workflow_primary, m.workflow_strict, m.workflow_alternative,
            r.workflow_primary as reason_category_workflow
        from silver.silver_call_center_interactions as i
        left join silver.silver_customers as c on c.customer_id = i.customer_id
        left join map_contact_reason as m on m.value = trim(i.contact_reason)
        left join map_reason_category as r on r.value = trim(i.reason_category)
        """
    ).df()


def surveys(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return connection.execute(
        "select interaction_id, survey_type, main_score from silver.silver_satisfaction_surveys "
        "where interaction_id is not null"
    ).df()


def complaints(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return connection.execute(
        """
        select
            k.complaint_id, k.creation_date, k.process_date, k.customer_id, k.case_type, k.category,
            k.subcategory, k.reception_channel, k.priority, k.status, k.sla_breached, k.resolution_days,
            k.is_repeat_complainer, k.compensation_granted, k.claimed_amount,
            c.country, c.segment, m.sub_intent, m.workflow_primary, m.workflow_strict, m.workflow_alternative
        from silver.silver_complaints as k
        left join silver.silver_customers as c on c.customer_id = k.customer_id
        left join map_complaint as m
            on m.value = trim(k.category) and m.subcategory = coalesce(trim(k.subcategory), '')
        """
    ).df()


def transcript_openings(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Transcript customer text reduced to its first sentence that mentions a balance, by contact reason (the
    intent-signal check)."""
    return connection.execute(
        """
        select
            contact_reason,
            coalesce(
                nullif(trim(regexp_extract(customer_text, '[^.?!]*saldo[^.?!]*[.?!]', 0)), ''),
                '(no balance sentence)'
            ) as opening,
            count(*) as transcripts
        from gold.interactions_with_transcripts
        where transcript_found
        group by all
        order by 1, 2
        """
    ).df()


def transcript_facts(connection: duckdb.DuckDBPyConnection) -> dict[str, int]:
    row = connection.execute(
        """
        select
            count(*) filter (where transcript_found),
            count(distinct customer_text) filter (where transcript_found),
            count(distinct detected_intents) filter (where transcript_found and detected_intents is not null),
            count(distinct main_topics) filter (where transcript_found and main_topics is not null),
            count(*) filter (where transcript_found and main_topics = contact_reason)
        from gold.interactions_with_transcripts
        """
    ).fetchone()
    values = [int(value or 0) for value in (row or (0, 0, 0, 0, 0))]
    keys = ("transcripts", "distinct_customer_texts", "distinct_detected_intents", "distinct_main_topics")
    facts = dict(zip(keys, values[:4], strict=True))
    facts["main_topics_equal_contact_reason"] = values[4]
    return facts


def detected_intent_values(connection: duckdb.DuckDBPyConnection) -> list[tuple[str, int]]:
    return [
        (str(value), int(count))
        for value, count in connection.execute(
            "select coalesce(detected_intents, '(null)'), count(*) from gold.interactions_with_transcripts "
            "where transcript_found group by 1 order by 2 desc limit 5"
        ).fetchall()
    ]


def labeling_candidates(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Interactions with a served transcript and customer text, with the primary workflow and country."""
    return connection.execute(
        """
        select t.interaction_id, m.workflow_primary as workflow, c.country, t.customer_text
        from gold.interactions_with_transcripts as t
        left join silver.silver_customers as c on c.customer_id = t.customer_id
        left join map_contact_reason as m on m.value = trim(t.contact_reason)
        where t.transcript_found and t.customer_text is not null and trim(t.customer_text) <> ''
        """
    ).df()


def _ratio(connection: duckdb.DuckDBPyConnection, sql: str) -> float | None:
    row = connection.execute(sql).fetchone()
    if row is None or row[1] is None or int(row[1]) == 0:
        return None
    return float(row[0] or 0) / float(row[1])


@dataclass(frozen=True)
class DataSupportItem:
    name: str
    description: str
    sql: str


DATA_SUPPORT_ITEMS: tuple[DataSupportItem, ...] = (
    DataSupportItem(
        "product_balance_present",
        "Non-closed products with a balance",
        "select count(current_balance), count(*) from silver.silver_products where product_status <> 'closed'",
    ),
    DataSupportItem(
        "transactions_classifiable_for_totals",
        "Transactions whose direction is encoded (not transfer or adjustment)",
        "select count(*) filter (where transaction_type not in ('transfer', 'adjustment')), count(*) "
        "from silver.silver_transactions",
    ),
    DataSupportItem(
        "payment_transfer_status_present",
        "Payments and transfers with a status",
        "select count(transaction_status), count(*) from silver.silver_transactions "
        "where transaction_type in ('payment', 'transfer')",
    ),
    DataSupportItem(
        "transaction_status_present",
        "Transactions with a status",
        "select count(transaction_status), count(*) from silver.silver_transactions",
    ),
    DataSupportItem(
        "card_expiry_present",
        "Credit and debit cards with an expiration date",
        "select count(expiration_date), count(*) from silver.silver_products "
        "where product_type in ('credit_card', 'debit_card')",
    ),
    DataSupportItem(
        "card_status_present",
        "Credit and debit cards with a status",
        "select count(product_status), count(*) from silver.silver_products "
        "where product_type in ('credit_card', 'debit_card')",
    ),
    DataSupportItem(
        "card_blocked_status_observed",
        "At least one blocked card (1 or 0)",
        "select least(count(*) filter (where product_status = 'blocked'), 1), 1 from silver.silver_products "
        "where product_type in ('credit_card', 'debit_card') having count(*) > 0",
    ),
    DataSupportItem(
        "purchase_merchant_present",
        "Purchases with a merchant name",
        "select count(merchant_name), count(*) from silver.silver_transactions where transaction_type = 'purchase'",
    ),
    DataSupportItem(
        "complaint_transaction_link_present",
        "Complaints with a transaction reference (no such column exists)",
        "select 0, count(*) from silver.silver_complaints",
    ),
    DataSupportItem(
        "complaint_own_product_reference",
        "Complaint product references that name the complainant's own product",
        "select count(*) filter (where not has_foreign_affected_product), count(*) from silver.silver_complaints "
        "where affected_product_id is not null",
    ),
    DataSupportItem(
        "complaint_claimed_amount_present",
        "Dispute-mapped complaints with a claimed amount",
        "select count(k.claimed_amount), count(*) from silver.silver_complaints as k "
        "join map_complaint as m on m.value = trim(k.category) and m.subcategory = coalesce(trim(k.subcategory), '') "
        "where m.workflow_primary = 'dispute'",
    ),
    DataSupportItem(
        "complaint_status_present",
        "Dispute-mapped complaints with a status",
        "select count(k.status), count(*) from silver.silver_complaints as k "
        "join map_complaint as m on m.value = trim(k.category) and m.subcategory = coalesce(trim(k.subcategory), '') "
        "where m.workflow_primary = 'dispute'",
    ),
    DataSupportItem(
        "customer_credit_score_present",
        "Customers with a credit score",
        "select count(credit_score), count(*) from silver.silver_customers",
    ),
    DataSupportItem(
        "customer_income_present",
        "Customers with an estimated monthly income",
        "select count(estimated_monthly_income), count(*) from silver.silver_customers",
    ),
    DataSupportItem(
        "credit_product_interest_rate_present",
        "Credit cards, personal loans, and mortgages with an interest rate",
        "select count(interest_rate), count(*) from silver.silver_products "
        "where product_type in ('credit_card', 'personal_loan', 'mortgage')",
    ),
    DataSupportItem(
        "credit_product_days_past_due_present",
        "Credit cards, personal loans, and mortgages with days past due",
        "select count(days_past_due), count(*) from silver.silver_products "
        "where product_type in ('credit_card', 'personal_loan', 'mortgage')",
    ),
    DataSupportItem(
        "forward_risk_label_available",
        "More than one snapshot of customers and products (1 or 0)",
        "select case when count(distinct snapshot_date) > 1 then 1 else 0 end, 1 from gold.credit_risk_inputs",
    ),
    DataSupportItem(
        "system_owned_record",
        "The record is created by the system itself (1)",
        "select 1, 1",
    ),
)


def data_support_values(connection: duckdb.DuckDBPyConnection, names: frozenset[str]) -> dict[str, float | None]:
    known = {item.name: item for item in DATA_SUPPORT_ITEMS}
    unknown = sorted(names - set(known))
    if unknown:
        raise KeyError(f"unknown data support items: {unknown}")
    return {name: _ratio(connection, known[name].sql) for name in sorted(names)}


def stop_condition_counts(connection: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Row counts behind the prompt's stop conditions for the core read paths and the credit profile."""
    queries = {
        "payment_or_transfer_transactions": (
            "select count(*) from silver.silver_transactions where transaction_type in ('payment', 'transfer')"
        ),
        "card_products": (
            "select count(*) from silver.silver_products where product_type in ('credit_card', 'debit_card')"
        ),
        "purchase_transactions": "select count(*) from silver.silver_transactions where transaction_type = 'purchase'",
        "credit_products_with_limit_or_rate": (
            "select count(*) from silver.silver_products "
            "where product_type in ('credit_card', 'personal_loan', 'mortgage') "
            "and (credit_limit is not null or interest_rate is not null)"
        ),
        "customers": "select count(*) from silver.silver_customers",
        "customers_with_credit_score": "select count(credit_score) from silver.silver_customers",
        "customers_with_income": "select count(estimated_monthly_income) from silver.silver_customers",
        "credit_products": (
            "select count(*) from silver.silver_products "
            "where product_type in ('credit_card', 'personal_loan', 'mortgage')"
        ),
        "credit_products_with_days_past_due": (
            "select count(days_past_due) from silver.silver_products "
            "where product_type in ('credit_card', 'personal_loan', 'mortgage')"
        ),
    }
    counts: dict[str, int] = {}
    for name, sql in queries.items():
        row = connection.execute(sql).fetchone()
        counts[name] = int(row[0] or 0) if row else 0
    return counts


def error_contact_lag(
    connection: duckdb.DuckDBPyConnection, *, window_hours: int, baseline_share: float, baseline_seed: str
) -> pd.DataFrame:
    """For digital events of known customers: error events, and a deterministic hash sample of other
    events, each with the hours to the same customer's next contact-center interaction (null when none
    follows within ``window_hours``) and that interaction's primary workflow.

    An as-of join finds the first interaction at or after the event. This measures association only.
    """
    buckets = 1_000_000
    threshold = round(baseline_share * buckets)
    return connection.execute(
        """
        with events as (
            select event_id, customer_id, event_date, event_type = 'error' as is_error, page_url
            from silver.stg_digital_events
            where customer_id is not null
              and (
                  event_type = 'error'
                  or cast(('0x' || left(md5($seed || event_id), 8)) as ubigint) % $buckets < $threshold
              )
        ),
        contacts as (
            select i.customer_id, i.interaction_date, m.workflow_primary as workflow
            from silver.silver_call_center_interactions as i
            left join map_contact_reason as m on m.value = trim(i.contact_reason)
        )
        select
            e.is_error,
            e.page_url,
            case when c.interaction_date <= e.event_date + to_hours($hours)
                 then date_diff('second', e.event_date, c.interaction_date) / 3600.0 end as hours_to_contact,
            case when c.interaction_date <= e.event_date + to_hours($hours)
                 then c.workflow end as contact_workflow
        from events as e
        asof left join contacts as c
            on c.customer_id = e.customer_id and c.interaction_date >= e.event_date
        """,
        {"seed": baseline_seed, "buckets": buckets, "threshold": threshold, "hours": int(window_hours)},
    ).df()
