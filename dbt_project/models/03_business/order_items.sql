-- order_items.sql
-- The backbone table: one row per item purchased, with price and revenue.
-- Joins carts with products to calculate what each item cost.

select
    c.cart_id,
    c.user_id,
    c.cart_date,
    c.product_id,
    p.title         as product_name,
    p.category,
    p.price         as unit_price,
    c.quantity,
    c.quantity * p.price as revenue
from {{ ref('stg_carts') }} c
join {{ ref('stg_products') }} p on c.product_id = p.product_id
