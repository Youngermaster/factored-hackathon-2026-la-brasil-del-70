{{ config(materialized='view') }}

select
    s.*,
    {{ orphan_flag('s', 'customer_id', 'customers', 'customer_id') }},
    {{ orphan_flag('s', 'affected_product_id', 'products', 'product_id') }},
    {{ orphan_flag('s', 'related_branch_id', 'branches', 'branch_id') }},
    {{ orphan_flag('s', 'origin_interaction_id', 'call_center_interactions', 'interaction_id') }},
    {{ orphan_flag('s', 'assigned_agent_id', 'service_agents', 'agent_id') }}
from {{ ref('stg_complaints') }} as s
