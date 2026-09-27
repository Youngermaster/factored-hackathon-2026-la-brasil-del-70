{#
  Customers for the demo database and the DuckDB read adapter. Personal data is limited to what the
  identity flow needs (first name for greetings; document type, document number, and mobile phone for the
  mock identity provider). Names beyond the first, emails, addresses, and birth dates are not served.
#}
{{ config(location=var('gold_dir') ~ '/customers_serving.parquet') }}

select
    customer_id,
    split_part(first_name, ' ', 1) as first_name,
    country,
    segment,
    customer_status,
    document_type,
    document_number,
    mobile_phone,
    cast('{{ var("snapshot_date") }}' as date) as snapshot_date
from {{ ref('silver_customers') }}
where country in ('MX', 'CO', 'AR')
order by customer_id
