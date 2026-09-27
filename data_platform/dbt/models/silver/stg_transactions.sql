{{
    config(
        materialized='incremental',
        unique_key='transaction_id',
        incremental_strategy='delete+insert',
        on_schema_change='fail',
    )
}}

{{ stg_body('transactions') }}
