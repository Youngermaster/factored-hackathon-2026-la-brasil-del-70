{#
  Products with masked numbers (last four characters only) and the snapshot instant of every balance.
  Credit balance convention (profiled in phase 03): current_balance is never negative and is the amount owed
  on credit products (balance_is_amount_owed). days_past_due and interest_rate are internal columns.
#}
{{ config(location=var('gold_dir') ~ '/products_serving.parquet') }}

with masked as (
    select
        *,
        upper(regexp_replace(product_number, '[^A-Za-z0-9]', '', 'g')) as number_characters
    from {{ ref('silver_products') }}
    where not is_orphan_customer_id
)

select
    product_id,
    customer_id,
    product_type,
    product_status,
    case when length(number_characters) >= 5 then right(number_characters, 4) end as product_number_last4,
    currency,
    current_balance,
    credit_limit,
    interest_rate,
    opening_date,
    expiration_date,
    days_past_due,
    {{ snapshot_end_utc() }} as balance_as_of,
    has_linked_app,
    product_type in ('credit_card', 'debit_card') as is_card,
    product_type in ('credit_card', 'personal_loan', 'mortgage') as is_credit_product,
    cast('{{ var("snapshot_date") }}' as date) as snapshot_date
from masked
order by customer_id, product_id
