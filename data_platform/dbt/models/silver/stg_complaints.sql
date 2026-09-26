{{
    config(
        materialized='incremental',
        unique_key='complaint_id',
        incremental_strategy='delete+insert',
        on_schema_change='fail',
    )
}}

{{ stg_body('complaints') }}
