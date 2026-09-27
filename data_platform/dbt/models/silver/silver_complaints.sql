{{ config(materialized='view') }}

select
    s.*,
    {{ orphan_flag('s', 'customer_id', 'customers', 'customer_id') }},
    {{ orphan_flag('s', 'affected_product_id', 'products', 'product_id') }},
    {{ orphan_flag('s', 'related_branch_id', 'branches', 'branch_id') }},
    {{ orphan_flag('s', 'origin_interaction_id', 'call_center_interactions', 'interaction_id') }},
    {{ orphan_flag('s', 'assigned_agent_id', 'service_agents', 'agent_id') }},
    coalesce(p.customer_id <> s.customer_id, false) as has_foreign_affected_product
from {{ ref('stg_complaints') }} as s
left join {{ ref('stg_products') }} as p on p.product_id = s.affected_product_id
