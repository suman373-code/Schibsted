-- stg_users.sql
-- Read user JSON directly from S3 stage and flatten into rows and columns.
-- Uses ROW_NUMBER to pick only the latest record per user_id (handles duplicate files).

with ranked as (
    select
        $1:id::int                            as user_id,
        $1:email::string                      as email,
        $1:username::string                   as username,
        $1:name.firstname::string             as first_name,
        $1:name.lastname::string              as last_name,
        $1:phone::string                      as phone,
        $1:address.city::string               as city,
        $1:address.street::string             as street,
        $1:address.number::int                as street_number,
        $1:address.zipcode::string            as zipcode,
        $1:address.geolocation.lat::string    as geo_lat,
        $1:address.geolocation.long::string   as geo_long,
        metadata$filename                     as source_file,
        row_number() over (partition by $1:id::int order by metadata$filename desc) as rn
    from {{ var('s3_stage') }}/users/
)

select
    user_id, email, username, first_name, last_name, phone,
    city, street, street_number, zipcode, geo_lat, geo_long
from ranked
where rn = 1
