{#
  Historical complaints limited to intake-time fields. Post-outcome fields (status, resolution, compensation,
  satisfaction, SLA breach) and the free-text description are not served: leakage and injection surfaces.
  affected_product_id is served only when it names the complaining customer's own product: in the delivery it
  always names another customer's product, so a served complaint never points across customers.
#}
{{ config(location=var('gold_dir') ~ '/complaints_serving.parquet') }}

select
    complaint_id,
    customer_id,
    creation_date as created_at,
    process_date,
    case_type,
    category,
    subcategory,
    reception_channel,
    case when not has_foreign_affected_product then affected_product_id end as affected_product_id,
    claimed_amount,
    currency,
    priority
from {{ ref('silver_complaints') }}
where not is_orphan_customer_id
order by customer_id, created_at, complaint_id
