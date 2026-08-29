-- Singular data test: all order amounts must be non-negative
select *
from {{ ref('stg_orders') }}
where amount_usd < 0
