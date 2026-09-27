{#
  Bronze access for silver models. Column metadata (type, canonical domain, keys) comes from the generated
  sources.yml, which `bank-data codegen` writes from bank_data.contracts.tables.
#}

{% macro bronze_node(table) -%}
    {%- set node = graph.sources.get('source.bank_data.bronze.' ~ table) -%}
    {%- if node is none -%}
        {{ exceptions.raise_compiler_error('unknown bronze table: ' ~ table) }}
    {%- endif -%}
    {{ return(node) }}
{%- endmacro %}

{% macro bronze_meta(table, key, default) -%}
    {%- if not execute -%}{{ return(default) }}{%- endif -%}
    {{ return(bronze_node(table).meta.get(key, default)) }}
{%- endmacro %}

{# Bronze rows of a table, limited to the sampled customers when `sample_customers` is set. #}
{% macro bronze_rows(table) -%}
    {%- set sampled = ref('sampled_customers') -%}
    {%- set customer_column = bronze_meta(table, 'customer_column', none) -%}
    select * from {{ source('bronze', table) }}
    {%- if var('sample_customers') | int > 0 and customer_column %}
    where nullif(trim("{{ customer_column }}"), '') in (select customer_id from {{ sampled }})
    {%- endif %}
{%- endmacro %}

{#
  The bronze rows an incremental fact model must (re)process:
  every process_date partition that received rows after the model's last load, plus a lookback window
  before the latest partition, and every version (in any partition) of the keys found there or of keys
  whose source object was reloaded. The model then replaces those keys (delete+insert on the primary key),
  so a partition arriving late, however old, is picked up and an incremental run equals a full rebuild.
#}
{% macro batch_rows(table) -%}
    {%- set key = bronze_meta(table, 'primary_key', ['id'])[0] -%}
    {%- if is_incremental() %}
    with bronze as (
        {{ bronze_rows(table) }}
    ),
    watermark as (
        select
            coalesce(max(_loaded_at), timestamp '1900-01-01') as loaded_at,
            coalesce(max(_process_date), date '1900-01-01') as latest
        from {{ this }}
    ),
    touched as (
        select distinct b._process_date
        from bronze as b, watermark as w
        where b._loaded_at > w.loaded_at
            or b._process_date >= w.latest - to_days({{ var('lookback_days') | int }})
    ),
    reloaded as (
        select distinct b._source_key from bronze as b, watermark as w where b._loaded_at > w.loaded_at
    ),
    batch_keys as (
        select distinct nullif(trim(b."{{ key }}"), '') as batch_key
        from bronze as b
        where b._process_date in (select _process_date from touched)
        union
        select t."{{ key }}" from {{ this }} as t where t._source_key in (select _source_key from reloaded)
    )
    select b.* from bronze as b where nullif(trim(b."{{ key }}"), '') in (select batch_key from batch_keys)
    {%- else %}
    {{ bronze_rows(table) }}
    {%- endif %}
{%- endmacro %}
