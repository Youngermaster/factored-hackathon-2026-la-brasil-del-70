{{
    config(
        materialized='incremental',
        unique_key='transcript_id',
        incremental_strategy='delete+insert',
        on_schema_change='fail',
    )
}}

{{ stg_body('call_transcripts') }}
