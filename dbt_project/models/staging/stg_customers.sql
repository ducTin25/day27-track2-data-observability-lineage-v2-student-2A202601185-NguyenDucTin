select
    cast(customer_id as varchar) as customer_id,
    cast(country as varchar) as country,
    cast(tier as varchar) as tier,
    cast(is_active as boolean) as is_active,
    cast(valid_from as timestamp) as valid_from,
    case when nullif(valid_to, '') is null then null else cast(valid_to as timestamp) end as valid_to
from {{ ref('customers') }}
