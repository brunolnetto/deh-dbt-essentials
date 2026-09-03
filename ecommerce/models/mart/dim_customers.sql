select
    customer_id,
    customer_name,
    email,
    country_code,
    country_name,
    region,
    currency,
    created_at,
    updated_at

from {{ ref('int_customers_enriched') }}
