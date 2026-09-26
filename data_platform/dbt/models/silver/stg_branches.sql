{{ config(materialized='table') }}

{{ stg_body('branches') }}
