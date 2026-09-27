{#
  Transactions for account inquiries, card support, and disputes. response_code, is_fraud, and fraud_score
  are internal columns: never shown to customers or sent to a model. merchant_name is untrusted text.
  Rows whose product or customer is missing are left out (they cannot be served as a customer's record).
#}
{{ config(location=var('gold_dir') ~ '/transactions_serving.parquet') }}

select
    transaction_id,
    customer_id,
    product_id,
    transaction_date as transaction_at,
    process_date,
    transaction_type,
    transaction_category,
    amount,
    currency,
    amount_usd,
    amount_usd_recomputed,
    channel,
    transaction_status,
    response_code,
    merchant_name,
    merchant_category,
    transaction_country as location_country,
    transaction_city as location_city,
    is_fraud,
    fraud_score
from {{ ref('silver_transactions') }}
where not is_orphan_product_id and not is_orphan_customer_id
order by customer_id, transaction_at, transaction_id
