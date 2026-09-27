{#
  Contact-center interactions joined to their transcript (left join on interaction_id). Input for the intent
  router work in phases 04 and 10. Profiling note: transcripts are templated (two opening sentences for every
  topic) and detected_intents is constant, so neither is a valid intent label.
#}
select
    i.interaction_id,
    i.interaction_date,
    i.process_date,
    i.customer_id,
    i.agent_id,
    i.interaction_type,
    i.channel,
    i.contact_reason,
    i.reason_category,
    i.duration_seconds,
    i.wait_time_seconds,
    i.was_resolved,
    i.requires_followup,
    i.detected_sentiment,
    i.sentiment_score,
    i.was_escalated,
    i.has_transcript,
    t.transcript_id,
    t.customer_text,
    t.agent_text,
    t.detected_language,
    t.detected_keywords,
    t.detected_intents,
    t.main_topics,
    t.audio_quality,
    t.transcript_id is not null as transcript_found
from {{ ref('silver_call_center_interactions') }} as i
left join {{ ref('silver_call_transcripts') }} as t on t.interaction_id = i.interaction_id
