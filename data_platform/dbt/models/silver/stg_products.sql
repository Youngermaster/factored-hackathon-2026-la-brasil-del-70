{{ config(materialized='table') }}

{{ stg_body('products') }}
