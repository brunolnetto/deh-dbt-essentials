{% set order_statuses = ['paid', 'cancelled', 'refunded'] %}

select
    customer_id,
    count(*) as total_orders,
    {% for s in order_statuses -%}
    {{ status_count('status', s) }} as {{ s }}_orders,
    {% endfor -%}
    sum(recognized_revenue) as revenue,
    sum(refunded_amount) as refunded_amount,
    avg(
        case
            when status = 'paid'
            then amount
        end
    ) as average_paid_order_value,
    min(order_date) as first_order_date,
    max(order_date) as last_order_date
from {{ ref('fct_orders') }}
where deleted_at is null
group by customer_id

