{# Daily contact-center volume and outcomes by contact reason and channel. Phase 04 adds the workflow mapping. #}
select
    process_date,
    contact_reason,
    reason_category,
    channel,
    interaction_type,
    count(*) as interactions,
    count(*) filter (where was_resolved) as resolved,
    count(*) filter (where was_escalated) as escalated,
    count(*) filter (where requires_followup) as requires_followup,
    count(*) filter (where detected_sentiment in ('negative', 'very_negative')) as negative_sentiment,
    avg(duration_seconds) as avg_duration_seconds,
    avg(wait_time_seconds) as avg_wait_seconds
from {{ ref('silver_call_center_interactions') }}
group by all
