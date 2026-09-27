{{ config(materialized='table') }}

{{ stg_body('daily_exchange_rates') }}
