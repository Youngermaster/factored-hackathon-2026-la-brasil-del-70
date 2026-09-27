{{ config(materialized='view') }}

select
    s.*,
    {{ orphan_flag('s', 'customer_id', 'customers', 'customer_id') }},
    {{ orphan_flag('s', 'opening_branch_id', 'branches', 'branch_id') }},
    s.last_updated > {{ snapshot_end_utc() }} as has_future_last_updated,
    count(*) over (partition by s.product_number) > 1 as has_duplicate_product_number
from {{ ref('stg_products') }} as s
