{{ config(materialized='view') }}

select
    s.*,
    {{ orphan_flag('s', 'customer_id', 'customers', 'customer_id') }},
    {{ orphan_flag('s', 'agent_id', 'service_agents', 'agent_id') }}
from {{ ref('stg_call_center_interactions') }} as s
