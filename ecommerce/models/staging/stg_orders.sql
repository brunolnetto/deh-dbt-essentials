select
    order_id,
    customer_id,
    cast(order_date as date) as order_date,
    cast(amount as numeric(12, 2)) as amount,
    lower(trim(status)) as status,
    created_at,
    updated_at,
    deleted_at
from {{ source('shop', 'orders') }}
