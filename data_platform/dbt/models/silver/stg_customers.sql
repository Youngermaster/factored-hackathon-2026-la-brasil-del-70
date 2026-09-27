{{ config(materialized='table') }}

{{ stg_body('customers') }}
