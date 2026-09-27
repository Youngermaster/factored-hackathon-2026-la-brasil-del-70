{{ config(materialized='view') }}

select s.*
from {{ ref('stg_daily_exchange_rates') }} as s
