-- Each cart should belong to exactly one user.
-- If any cart_id maps to more than one user_id, something is wrong in the source data.
-- dbt treats this as a failure if any rows are returned.

SELECT
    cart_id,
    COUNT(DISTINCT user_id) AS user_count
FROM {{ ref('stg_carts') }}
GROUP BY cart_id
HAVING COUNT(DISTINCT user_id) > 1
