{# Monthly SLA performance of complaints by priority and category (post-outcome fields; analytics only). #}
select
    cast(date_trunc('month', creation_date) as date) as month,
    priority,
    category,
    count(*) as complaints,
    count(*) filter (where sla_breached) as sla_breached,
    round(count(*) filter (where sla_breached) / count(*), 4) as sla_breach_rate,
    avg(resolution_days) as avg_resolution_days,
    median(date_diff('minute', creation_date, first_response_date) / 60.0) as median_first_response_hours
from {{ ref('silver_complaints') }}
group by all
