{{ config(materialized='table') }}

{{ stg_body('marketing_campaigns') }}
