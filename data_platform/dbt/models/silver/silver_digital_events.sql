{{ config(materialized='view') }}

select
    s.*,
    {{ orphan_flag('s', 'customer_id', 'customers', 'customer_id') }},
    {{ orphan_flag('s', 'product_id', 'products', 'product_id') }},
    coalesce(p.customer_id <> s.customer_id, false) as has_foreign_product
from {{ ref('stg_digital_events') }} as s
left join {{ ref('stg_products') }} as p on p.product_id = s.product_id
