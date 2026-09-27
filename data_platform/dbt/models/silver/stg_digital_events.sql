{{
    config(
        materialized='incremental',
        unique_key='event_id',
        incremental_strategy='delete+insert',
        on_schema_change='fail',
    )
}}

{{ stg_body('digital_events') }}
