{{ config(materialized='view') }}

select
    s.*,
    {{ orphan_flag('s', 'campaign_id', 'marketing_campaigns', 'campaign_id') }},
    {{ orphan_flag('s', 'customer_id', 'customers', 'customer_id') }}
from {{ ref('stg_campaign_sends') }} as s
