select
    cast(order_id as bigint) as order_id,
    cast(customer_id as varchar) as customer_id,
    cast(amount as double) as amount_usd,
    cast(currency as varchar) as currency,
    cast(status as varchar) as status,
    cast(created_at as timestamp) as created_at,
    cast(updated_at as timestamp) as updated_at,
    cast(created_at as date) as order_date
from {{ ref('orders') }}
