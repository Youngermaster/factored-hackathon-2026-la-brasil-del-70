{{ config(materialized='view') }}

select s.*
from {{ ref('stg_marketing_campaigns') }} as s
