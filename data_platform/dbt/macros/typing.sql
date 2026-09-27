{# Typing, trimming, and empty-to-null for bronze strings, driven by the column metadata in sources.yml. #}

{% macro snake(expression) -%}
    lower(trim(regexp_replace({{ expression }}, '[^A-Za-z0-9]+', '_', 'g'), '_'))
{%- endmacro %}

{% macro canonical(domain, expression) -%}
    {%- if domain == 'identity' -%}
        {{ expression }}
    {%- elif domain == 'snake' -%}
        {{ snake(expression) }}
    {%- else -%}
        coalesce(
            (select cv.canonical from {{ ref('canonical_values') }} as cv
             where cv.domain = '{{ domain }}' and cv.source_value = {{ expression }}),
            {{ snake(expression) }}
        )
    {%- endif -%}
{%- endmacro %}

{% macro typed_expression(expression, meta) -%}
    {%- set cleaned = "nullif(trim(" ~ expression ~ "), '')" -%}
    {%- set dtype = meta.get('dtype') -%}
    {%- if dtype == 'string' -%}
        {%- if meta.get('canonical') -%}{{ canonical(meta.get('canonical'), cleaned) }}{%- else -%}{{ cleaned }}{%- endif -%}
    {%- elif dtype == 'integer' -%}
        cast(cast({{ cleaned }} as decimal(38, 6)) as bigint)
    {%- elif dtype == 'boolean' -%}
        cast(lower({{ cleaned }}) as boolean)
    {%- else -%}
        cast({{ cleaned }} as {{ meta.get('silver_type') }})
    {%- endif -%}
{%- endmacro %}

{% macro typed_select(table, alias) -%}
    {%- set seed = ref('canonical_values') -%}
    {%- if execute -%}
        {%- set node = bronze_node(table) -%}
        {%- set excluded = node.meta.get('silver_exclude', []) -%}
        {%- for name, column in node.columns.items() if name not in excluded %}
        {{ typed_expression(alias ~ '."' ~ name ~ '"', column.meta) }} as "{{ name }}",
        {%- endfor %}
    {%- endif %}
        {{ alias }}._source_key,
        {{ alias }}._etag,
        {{ alias }}._loaded_at,
        {{ alias }}._process_date,
        {{ alias }}._source_row
{%- endmacro %}

{#
  Primary-key duplicates keep the latest order column (last_updated or process_date); ties break on the
  greatest _etag, then _source_key, then the later row in the object. Exact duplicates are a special case.
#}
{% macro deduplicate(relation, table) -%}
    {%- set keys = bronze_meta(table, 'primary_key', ['id']) -%}
    {%- set order_column = bronze_meta(table, 'order_column', '_process_date') -%}
    select * exclude (_dedup_rank)
    from (
        select
            *,
            row_number() over (
                partition by {% for key in keys %}"{{ key }}"{{ ", " if not loop.last }}{% endfor %}
                order by "{{ order_column }}" desc nulls last, _etag desc, _source_key desc, _source_row desc
            ) as _dedup_rank
        from {{ relation }}
    )
    where _dedup_rank = 1
{%- endmacro %}

{# The body of every stg_ model: typed bronze rows (the incremental batch for facts), deduplicated. #}
{% macro stg_body(table) -%}
    with batch as (
        {{ batch_rows(table) }}
    ),
    typed as (
        select
            {{ typed_select(table, 'batch') }}
        from batch
    )
    {{ deduplicate('typed', table) }}
{%- endmacro %}

{% macro orphan_flag(alias, column, parent, parent_column) -%}
    ({{ alias }}."{{ column }}" is not null and not exists (
        select 1 from {{ ref('stg_' ~ parent) }} as parent where parent."{{ parent_column }}" = {{ alias }}."{{ column }}"
    )) as "is_orphan_{{ column }}"
{%- endmacro %}

{# The end of the snapshot business day (UTC-6) as a UTC timestamp. #}
{% macro snapshot_end_utc() -%}
    (cast('{{ var("snapshot_date") }}' as date) + interval 1 day + interval 6 hour - interval 1 second)
{%- endmacro %}

{#
  amount_usd where it is missing: USD amounts at rate 1; other currencies at the latest USD rate on or before
  the business date (as-of join). Yields every transaction column plus `recomputed_usd`.
#}
{% macro with_recomputed_usd(transactions, rates) -%}
    select
        t.*,
        case
            when t.currency = 'USD' then t.amount
            else round(t.amount * r.exchange_rate, 2)
        end as recomputed_usd
    from {{ transactions }} as t
    asof left join (
        select date as rate_date, source_currency, exchange_rate from {{ rates }} where target_currency = 'USD'
    ) as r
        on r.source_currency = t.currency and t.process_date >= r.rate_date
{%- endmacro %}
