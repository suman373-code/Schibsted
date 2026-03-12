-- stg_carts.sql
-- Read cart JSON directly from S3 stage and flatten: one row per product in a cart.
-- Uses ROW_NUMBER to pick only the latest record per cart_id + product_id (handles duplicate files).

with flattened as (
    select
        s.$1:id::int                  as cart_id,
        s.$1:userId::int              as user_id,
        s.$1:date::date               as cart_date,
        item.value:productId::int     as product_id,
        item.value:quantity::int      as quantity,
        s.metadata$filename           as source_file
    from {{ var('s3_stage') }}/carts/ s,
        lateral flatten(input => s.$1:products) as item
),

ranked as (
    select
        cart_id, user_id, cart_date, product_id, quantity,
        row_number() over (partition by cart_id, product_id order by source_file desc) as rn
    from flattened
)

select
    cart_id, user_id, cart_date, product_id, quantity
from ranked
where rn = 1
