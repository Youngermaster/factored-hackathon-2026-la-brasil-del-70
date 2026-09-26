{#
  Event timestamps are UTC and process_date is the UTC-6 business date, so an event may fall on the next
  calendar day. Fails for rows whose timestamp date is more than `days` after process_date.
#}
{% test not_after_process_date(model, column_name, days=1) %}
select *
from {{ model }}
where cast({{ column_name }} as date) > process_date + to_days({{ days | int }})
{% endtest %}
