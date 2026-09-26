{{ config(materialized='view') }}

select
    s.*,
    {{ orphan_flag('s', 'assigned_branch_id', 'branches', 'branch_id') }},
    count(*) over (partition by s.employee_code) > 1 as has_duplicate_employee_code
from {{ ref('stg_service_agents') }} as s
