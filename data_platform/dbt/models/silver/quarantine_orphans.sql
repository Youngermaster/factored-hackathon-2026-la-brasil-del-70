{# Every silver row whose foreign key has no parent row. Orphans stay in silver (flagged); this view lists them. #}
{{ config(materialized='view') }}

{%- set checks = [
    ('customers', 'customer_id', 'registration_branch_id', 'branches'),
    ('products', 'product_id', 'customer_id', 'customers'),
    ('products', 'product_id', 'opening_branch_id', 'branches'),
    ('service_agents', 'agent_id', 'assigned_branch_id', 'branches'),
    ('transactions', 'transaction_id', 'product_id', 'products'),
    ('transactions', 'transaction_id', 'customer_id', 'customers'),
    ('transactions', 'transaction_id', 'branch_id', 'branches'),
    ('call_center_interactions', 'interaction_id', 'customer_id', 'customers'),
    ('call_center_interactions', 'interaction_id', 'agent_id', 'service_agents'),
    ('call_transcripts', 'transcript_id', 'interaction_id', 'call_center_interactions'),
    ('call_transcripts', 'transcript_id', 'customer_id', 'customers'),
    ('call_transcripts', 'transcript_id', 'agent_id', 'service_agents'),
    ('satisfaction_surveys', 'survey_id', 'interaction_id', 'call_center_interactions'),
    ('satisfaction_surveys', 'survey_id', 'customer_id', 'customers'),
    ('satisfaction_surveys', 'survey_id', 'agent_id', 'service_agents'),
    ('digital_events', 'event_id', 'customer_id', 'customers'),
    ('digital_events', 'event_id', 'product_id', 'products'),
    ('complaints', 'complaint_id', 'customer_id', 'customers'),
    ('complaints', 'complaint_id', 'affected_product_id', 'products'),
    ('complaints', 'complaint_id', 'related_branch_id', 'branches'),
    ('complaints', 'complaint_id', 'origin_interaction_id', 'call_center_interactions'),
    ('complaints', 'complaint_id', 'assigned_agent_id', 'service_agents'),
    ('campaign_sends', 'send_id', 'campaign_id', 'marketing_campaigns'),
    ('campaign_sends', 'send_id', 'customer_id', 'customers'),
] %}

{% for table, key, column, parent in checks %}
select
    '{{ table }}' as table_name,
    cast("{{ key }}" as varchar) as row_key,
    '{{ column }}' as fk_column,
    cast("{{ column }}" as varchar) as fk_value,
    '{{ parent }}' as referenced_table
from {{ ref('silver_' ~ table) }}
where "is_orphan_{{ column }}"
{% if not loop.last %}union all{% endif %}
{% endfor %}
