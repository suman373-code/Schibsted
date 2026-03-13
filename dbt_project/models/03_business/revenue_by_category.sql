-- revenue_by_category.sql
--how does each product category perform?
-- Great for dashboards and trend analysis.

with orders as (
    select * from {{ ref('order_items') }}
)

select
    category,
    count(distinct cart_id)     as total_orders,
    count(distinct user_id)     as unique_customers,
    sum(quantity)               as total_items_sold,
    round(sum(revenue), 2)      as total_revenue,
    round(avg(unit_price), 2)        as avg_product_price,
    round(sum(revenue) / nullif(count(distinct user_id), 0), 2) as revenue_per_customer,
    count(distinct product_id)  as unique_products_sold
from orders
group by category
order by total_revenue desc
