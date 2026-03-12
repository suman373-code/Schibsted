-- stg_products.sql
-- Read product JSON directly from S3 stage and flatten into rows and columns.
-- Uses ROW_NUMBER to pick only the latest record per product_id (handles duplicate files).

with ranked as (
    select
        $1:id::int                as product_id,
        $1:title::string          as title,
        $1:price::float           as price,
        $1:category::string       as category,
        $1:description::string    as description,
        $1:image::string          as image_url,
        $1:rating.rate::float     as rating,
        $1:rating.count::int      as rating_count,
        metadata$filename         as source_file,
        row_number() over (partition by $1:id::int order by metadata$filename desc) as rn
    from {{ var('s3_stage') }}/products/
)

select
    product_id, title, price, category, description, image_url, rating, rating_count
from ranked
where rn = 1
