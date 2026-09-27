{#
  Customer-level credit features per snapshot date, with days past due kept in separate columns so phase 10
  can build a label strictly after its features. Features use only data up to the snapshot date. Protected
  and proxy attributes (gender, birth date, marital status, accent, location below country, segment,
  occupation, education) are deliberately absent. The delivery has one snapshot (see source-layout.md).
#}
with snapshot as (
    select cast('{{ var("snapshot_date") }}' as date) as snapshot_date
),

products as (
    select *
    from {{ ref('silver_products') }}
    where product_status <> 'closed' and not is_orphan_customer_id
),

product_features as (
    select
        customer_id,
        count(*) as product_count,
        count(*) filter (where product_type = 'credit_card') as credit_card_count,
        count(*) filter (where product_type in ('personal_loan', 'mortgage')) as loan_count,
        count(*) filter (where product_type in ('checking_account', 'savings_account')) as deposit_account_count,
        max(days_past_due) as max_days_past_due,
        count(*) filter (where days_past_due >= 30) as products_30_plus_days_past_due
    from products
    group by customer_id
),

transaction_features as (
    select
        t.customer_id,
        count(*) as transactions_90d,
        sum(t.amount_usd) filter (where t.transaction_status = 'approved') as approved_amount_usd_90d,
        count(*) filter (where t.transaction_status = 'declined') as declined_90d,
        count(*) filter (where t.transaction_type = 'payment') as payments_90d
    from {{ ref('silver_transactions') }} as t, snapshot as s
    where t.process_date > s.snapshot_date - interval 90 day and t.process_date <= s.snapshot_date
    group by t.customer_id
),

complaint_features as (
    select k.customer_id, count(*) as complaints_365d
    from {{ ref('silver_complaints') }} as k, snapshot as s
    where k.process_date > s.snapshot_date - interval 365 day and k.process_date <= s.snapshot_date
    group by k.customer_id
),

profiles as (
    select * from {{ ref('credit_profiles_serving') }}
)

select
    c.customer_id,
    s.snapshot_date,
    c.country,
    pr.credit_score,
    pr.estimated_monthly_income,
    pr.income_currency,
    pr.tenure_months,
    coalesce(pf.product_count, 0) as product_count,
    coalesce(pf.credit_card_count, 0) as credit_card_count,
    coalesce(pf.loan_count, 0) as loan_count,
    coalesce(pf.deposit_account_count, 0) as deposit_account_count,
    pr.total_credit_limit,
    pr.total_credit_limit_currency,
    pr.utilization,
    coalesce(tf.transactions_90d, 0) as transactions_90d,
    coalesce(tf.approved_amount_usd_90d, 0) as approved_amount_usd_90d,
    coalesce(tf.declined_90d, 0) as declined_90d,
    coalesce(tf.payments_90d, 0) as payments_90d,
    coalesce(cf.complaints_365d, 0) as complaints_365d,
    pf.max_days_past_due as days_past_due_at_snapshot,
    coalesce(pf.products_30_plus_days_past_due, 0) as products_30_plus_days_past_due_at_snapshot
from {{ ref('silver_customers') }} as c
cross join snapshot as s
left join profiles as pr on pr.customer_id = c.customer_id
left join product_features as pf on pf.customer_id = c.customer_id
left join transaction_features as tf on tf.customer_id = c.customer_id
left join complaint_features as cf on cf.customer_id = c.customer_id
