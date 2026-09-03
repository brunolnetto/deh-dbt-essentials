select
    c.customer_id,
    c.customer_name,
    c.email,
    c.country_code,
    cc.country_name,
    cc.region,
    cc.currency,
    c.created_at,
    c.updated_at

from {{ ref('stg_customers') }} as c
left join {{ ref('country_codes') }} as cc
    on c.country_code = cc.country_code

