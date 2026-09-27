{{
    config(
        materialized='incremental',
        unique_key='send_id',
        incremental_strategy='delete+insert',
        on_schema_change='fail',
    )
}}

{{ stg_body('campaign_sends') }}
