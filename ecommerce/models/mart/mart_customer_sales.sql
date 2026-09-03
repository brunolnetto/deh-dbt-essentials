{{ config(tags=['marts', 'finance']) }}

select
    c.customer_id,
    c.customer_name,
    c.email,
    c.country_code,
    c.country_name,
    c.region,
    c.currency,
    coalesce(o.total_orders, 0) as total_orders,
    coalesce(o.paid_orders, 0) as paid_orders,
    coalesce(o.cancelled_orders, 0) as cancelled_orders,
    coalesce(o.refunded_orders, 0) as refunded_orders,
    coalesce(o.revenue, 0) as revenue,
    coalesce(o.refunded_amount, 0) as refunded_amount,
    o.average_paid_order_value,
    o.first_order_date,
    o.last_order_date
from {{ ref('dim_customers') }} c
left join {{ ref('int_orders_by_customer') }} o
    on c.customer_id = o.customer_id
