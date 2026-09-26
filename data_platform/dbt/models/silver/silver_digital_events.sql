{{ config(materialized='view') }}

select
    s.*,
    {{ orphan_flag('s', 'customer_id', 'customers', 'customer_id') }},
    {{ orphan_flag('s', 'product_id', 'products', 'product_id') }}
from {{ ref('stg_digital_events') }} as s
