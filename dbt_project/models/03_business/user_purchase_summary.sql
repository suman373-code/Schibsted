-- user_purchase_summary.sql
-- THE key metric table: everything about each user's buying behavior.
-- This is what a business analyst or ML model would look at.

with orders as (
    select * from {{ ref('order_items') }}
),

-- Per-user totals
user_totals as (
    select
        user_id,
        count(distinct cart_id)     as total_orders,
        count(*)                    as total_items_purchased,
        round(sum(revenue), 2)      as total_spend,
        round(avg(revenue), 2)      as avg_item_spend,
        count(distinct category)    as unique_categories_bought,
        min(cart_date)              as first_order_date,
        max(cart_date)              as last_order_date
    from orders
    group by user_id
),

-- Find each user's favorite category (most items bought)
category_ranked as (
    select
        user_id,
        category,
        sum(quantity) as items_in_category,
        row_number() over (
            partition by user_id
            order by sum(quantity) desc
        ) as rank
    from orders
    group by user_id, category
),

favorite as (
    select user_id, category as favorite_category
    from category_ranked
    where rank = 1
)

-- Put it all together
select
    t.user_id,
    t.total_orders,
    t.total_items_purchased,
    t.total_spend,
    t.avg_item_spend,
    round(t.total_spend / nullif(t.total_orders, 0), 2) as avg_order_value,
    t.unique_categories_bought,
    f.favorite_category,
    t.first_order_date,
    t.last_order_date
from user_totals t
left join favorite f on t.user_id = f.user_id
