{{ config(materialized='view') }}

select
    s.*,
    count(*) over (partition by s.branch_code) > 1 as has_duplicate_branch_code
from {{ ref('stg_branches') }} as s
