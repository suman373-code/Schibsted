-- user_features.sql
-- Feature table for ML: combines user purchase behavior with location data.
-- Used by Snowflake Cortex ML to predict which category a user prefers.

select
    s.user_id,
    s.total_orders,
    s.total_items_purchased,
    s.total_spend,
    s.avg_item_spend,
    s.avg_order_value,
    s.favorite_category,
    s.unique_categories_bought,
    u.city
from {{ ref('user_purchase_summary') }} s
join {{ ref('stg_users') }} u on s.user_id = u.user_id
