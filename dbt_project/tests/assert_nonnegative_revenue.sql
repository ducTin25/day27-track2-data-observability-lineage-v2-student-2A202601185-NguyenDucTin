-- A singular data test: query returns zero rows when the assertion passes.
select *
from {{ ref('fct_daily_revenue') }}
where daily_revenue < 0
