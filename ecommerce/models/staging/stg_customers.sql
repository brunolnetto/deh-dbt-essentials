select
    customer_id,
    trim(name) as customer_name,
    lower(trim(email)) as email,
    upper(trim(country_code)) as country_code,
    created_at,
    updated_at

from {{ source('shop', 'customers') }}

