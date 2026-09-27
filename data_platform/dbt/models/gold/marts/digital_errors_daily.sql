{# Daily digital error events and error rate by channel, platform, and page. #}
select
    process_date,
    channel,
    platform,
    page_url,
    count(*) as events,
    count(*) filter (where event_type = 'error') as errors,
    round(count(*) filter (where event_type = 'error') / count(*), 4) as error_rate
from {{ ref('silver_digital_events') }}
group by all
