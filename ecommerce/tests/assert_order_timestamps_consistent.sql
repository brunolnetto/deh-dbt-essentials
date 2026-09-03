select
    order_id,
    created_at,
    updated_at

from {{ ref('stg_orders') }}

where updated_at < created_at
