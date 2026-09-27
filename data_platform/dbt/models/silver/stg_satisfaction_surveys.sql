{{
    config(
        materialized='incremental',
        unique_key='survey_id',
        incremental_strategy='delete+insert',
        on_schema_change='fail',
    )
}}

{{ stg_body('satisfaction_surveys') }}
