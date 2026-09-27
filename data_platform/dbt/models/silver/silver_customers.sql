{{ config(materialized='view') }}

select
    s.*,
    {{ orphan_flag('s', 'registration_branch_id', 'branches', 'branch_id') }},
    s.last_updated > {{ snapshot_end_utc() }} as has_future_last_updated
from {{ ref('stg_customers') }} as s
