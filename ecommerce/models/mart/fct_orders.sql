{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge',
    tags=['finance', 'incremental']
) }}

select
    order_id,
    customer_id,
    order_date,
    status,
    amount,

    case when status = 'paid' then 1 else 0 end as is_paid,
    case when status = 'cancelled' then 1 else 0 end as is_cancelled,
    case when status = 'refunded' then 1 else 0 end as is_refunded,

    {{ amount_for_status('amount', 'status', 'paid') }} as recognized_revenue,
    {{ amount_for_status('amount', 'status', 'refunded') }} as refunded_amount,

    created_at,
    updated_at,
    deleted_at

from {{ ref('stg_orders') }}

{% if is_incremental() %}
where updated_at > (
    select coalesce(max(updated_at), '1900-01-01'::timestamptz)
    from {{ this }}
)
{% endif %}

