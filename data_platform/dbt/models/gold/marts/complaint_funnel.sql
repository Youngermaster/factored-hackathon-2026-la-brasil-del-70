{# Monthly complaint funnel: created, assigned, first response, resolved, closed, by category and case type. #}
select
    cast(date_trunc('month', creation_date) as date) as month,
    category,
    case_type,
    priority,
    count(*) as created,
    count(*) filter (where assignment_date is not null) as assigned,
    count(*) filter (where first_response_date is not null) as first_responded,
    count(*) filter (where resolution_date is not null) as resolved,
    count(*) filter (where closing_date is not null) as closed,
    count(*) filter (where status = 'escalated') as escalated,
    count(*) filter (where status = 'rejected') as rejected
from {{ ref('silver_complaints') }}
group by all
