select
    order_id,
    customer_id,
    amount,
    status

from {{ ref('stg_orders') }}

where amount <= 0

