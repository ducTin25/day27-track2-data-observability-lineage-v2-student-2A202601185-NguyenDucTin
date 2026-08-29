-- Singular data test: detect revenue inflation from SCD customer dimension.
-- If a customer has multiple active rows, the LEFT JOIN in fct_daily_revenue
-- will multiply revenue for that customer's orders.
-- This test checks that no order_date has more completed orders than
-- the number of distinct order_ids in stg_orders for that date.

with order_counts as (
    select
        order_date,
        count(distinct order_id) as distinct_orders
    from {{ ref('stg_orders') }}
    where status = 'completed'
    group by 1
),
revenue_counts as (
    select
        order_date,
        completed_order_rows
    from {{ ref('fct_daily_revenue') }}
)
select
    r.order_date,
    r.completed_order_rows,
    o.distinct_orders
from revenue_counts r
left join order_counts o
    on r.order_date = o.order_date
where r.completed_order_rows > o.distinct_orders
