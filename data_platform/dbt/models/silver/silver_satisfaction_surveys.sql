{{ config(materialized='view') }}

select
    s.*,
    {{ orphan_flag('s', 'interaction_id', 'call_center_interactions', 'interaction_id') }},
    {{ orphan_flag('s', 'customer_id', 'customers', 'customer_id') }},
    {{ orphan_flag('s', 'agent_id', 'service_agents', 'agent_id') }}
from {{ ref('stg_satisfaction_surveys') }} as s
