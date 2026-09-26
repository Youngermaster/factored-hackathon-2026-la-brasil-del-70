{#
  The deterministic customer sample: when `sample_customers` is N > 0, the N customers with the smallest
  sha256(seed || ':' || customer_id). Every customer-scoped silver table follows this list. Empty otherwise.
#}
{{ config(materialized='table') }}

{% if var('sample_customers') | int > 0 %}
select customer_id
from (
    select distinct nullif(trim(customer_id), '') as customer_id
    from {{ source('bronze', 'customers') }}
)
where customer_id is not null
order by sha256('{{ var("sample_seed") }}' || ':' || customer_id), customer_id
limit {{ var('sample_customers') | int }}
{% else %}
select cast(null as varchar) as customer_id
where false
{% endif %}
