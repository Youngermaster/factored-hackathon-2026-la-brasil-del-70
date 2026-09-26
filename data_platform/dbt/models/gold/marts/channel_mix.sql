{# Monthly volume by channel across contact-center interactions, digital events, and complaints. #}
select cast(date_trunc('month', process_date) as date) as month, 'contact_center' as source, channel, count(*) as volume
from {{ ref('silver_call_center_interactions') }}
group by all
union all
select cast(date_trunc('month', process_date) as date) as month, 'digital' as source, channel, count(*) as volume
from {{ ref('silver_digital_events') }}
group by all
union all
select cast(date_trunc('month', process_date) as date) as month, 'complaints' as source, reception_channel as channel, count(*) as volume
from {{ ref('silver_complaints') }}
group by all
