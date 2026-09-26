{#
  One credit profile per customer at the snapshot date. Credit products are credit cards, personal loans,
  and mortgages that are not closed. credit_score, estimated_monthly_income, max_days_past_due, and
  utilization are internal columns. Missing facts stay null; nothing is imputed.

  - tenure_months: whole months from registration_date to the snapshot date;
  - total_credit_limit: sum of the credit products' limits, only when they share one currency;
  - utilization: credit-card balance over credit-card limit (revolving utilization), one currency only;
  - income_currency: the country currency (the dictionary states income in local currency).
#}
{{ config(location=var('gold_dir') ~ '/credit_profiles_serving.parquet') }}

with credit as (
    select *
    from {{ ref('silver_products') }}
    where product_type in ('credit_card', 'personal_loan', 'mortgage')
        and product_status <> 'closed'
        and not is_orphan_customer_id
),

per_customer as (
    select
        customer_id,
        count(*) as credit_product_count,
        max(days_past_due) as max_days_past_due,
        count(distinct currency) filter (where credit_limit is not null) as limit_currencies,
        sum(credit_limit) as limit_total,
        any_value(currency) filter (where credit_limit is not null) as limit_currency,
        count(distinct currency) filter (where product_type = 'credit_card' and credit_limit > 0) as card_currencies,
        sum(current_balance) filter (where product_type = 'credit_card' and credit_limit > 0) as card_balance,
        sum(credit_limit) filter (where product_type = 'credit_card' and credit_limit > 0) as card_limit
    from credit
    group by customer_id
)

select
    c.customer_id,
    c.credit_score,
    c.estimated_monthly_income,
    case c.country when 'MX' then 'MXN' when 'CO' then 'COP' when 'AR' then 'ARS' end as income_currency,
    cast(date_sub('month', cast(c.registration_date as date), cast('{{ var("snapshot_date") }}' as date)) as bigint)
        as tenure_months,
    coalesce(p.credit_product_count, 0) as credit_product_count,
    p.max_days_past_due,
    case when p.limit_currencies = 1 then p.limit_total end as total_credit_limit,
    case when p.limit_currencies = 1 then p.limit_currency end as total_credit_limit_currency,
    case when p.card_currencies = 1 then cast(round(p.card_balance / p.card_limit, 4) as decimal(12, 4)) end
        as utilization,
    cast('{{ var("snapshot_date") }}' as date) as snapshot_date
from {{ ref('silver_customers') }} as c
left join per_customer as p on p.customer_id = c.customer_id
where c.country in ('MX', 'CO', 'AR')
order by c.customer_id
