{{ config(materialized='view') }}

{#
  amount_usd is recomputed where it is null: USD rows use rate 1, other currencies the latest USD rate on or
  before the business date (as-of join). transaction_local_time shows the UTC timestamp in the customer's
  country zone.
#}
with enriched as (
    {{ with_recomputed_usd(ref('stg_transactions'), ref('stg_daily_exchange_rates')) }}
)

select
    s.* exclude (recomputed_usd) replace (
        cast(coalesce(s.amount_usd, s.recomputed_usd) as decimal(15, 2)) as amount_usd
    ),
    {{ orphan_flag('s', 'product_id', 'products', 'product_id') }},
    {{ orphan_flag('s', 'customer_id', 'customers', 'customer_id') }},
    {{ orphan_flag('s', 'branch_id', 'branches', 'branch_id') }},
    (s.amount_usd is null and s.recomputed_usd is not null) as amount_usd_recomputed,
    timezone(
        case c.country
            when 'MX' then 'America/Mexico_City'
            when 'CO' then 'America/Bogota'
            when 'AR' then 'America/Argentina/Buenos_Aires'
        end,
        cast(s.transaction_date as timestamptz)
    ) as transaction_local_time
from enriched as s
left join {{ ref('stg_customers') }} as c on c.customer_id = s.customer_id
