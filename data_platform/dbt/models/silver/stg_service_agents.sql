{{ config(materialized='table') }}

{{ stg_body('service_agents') }}
