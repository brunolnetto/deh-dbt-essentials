select
    c.customer_id,
    c.customer_name,
    c.country_code

from {{ ref('stg_customers') }} as c

left join {{ ref('country_codes') }} as cc
    on c.country_code = cc.country_code

where cc.country_code is null

