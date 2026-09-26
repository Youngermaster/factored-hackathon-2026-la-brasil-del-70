{#
  Complaints with product and customer context. Intake-time fields keep their names; post-outcome fields
  carry the outcome_ prefix so they can serve as labels and are never mistaken for intake-time features.
#}
select
    k.complaint_id,
    k.creation_date,
    k.process_date,
    k.customer_id,
    k.case_type,
    k.category,
    k.subcategory,
    k.reception_channel,
    k.affected_product_id,
    p.product_type as affected_product_type,
    p.product_status as affected_product_status,
    k.claimed_amount,
    k.currency,
    k.priority,
    k.is_repeat_complainer,
    k.description,
    c.country as customer_country,
    c.segment as customer_segment,
    cast(date_sub('month', cast(c.registration_date as date), k.process_date) as bigint) as customer_tenure_months,
    k.status as outcome_status,
    k.assignment_date as outcome_assignment_date,
    k.first_response_date as outcome_first_response_date,
    k.resolution_date as outcome_resolution_date,
    k.closing_date as outcome_closing_date,
    k.sla_breached as outcome_sla_breached,
    k.resolution_days as outcome_resolution_days,
    k.resolution as outcome_resolution,
    k.compensation_granted as outcome_compensation_granted,
    k.resolution_satisfaction as outcome_resolution_satisfaction
from {{ ref('silver_complaints') }} as k
left join {{ ref('silver_products') }} as p on p.product_id = k.affected_product_id
left join {{ ref('silver_customers') }} as c on c.customer_id = k.customer_id
