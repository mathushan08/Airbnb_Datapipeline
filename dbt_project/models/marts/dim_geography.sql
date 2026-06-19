-- models/marts/dim_geography.sql
WITH geo AS (
    SELECT
        id AS listing_id,
        neighbourhood_cleansed AS neighbourhood,
        neighbourhood_group_cleansed AS neighbourhood_group,
        latitude,
        longitude
    FROM {{ ref('stg_listings') }}
)

SELECT * FROM geo
