-- models/marts/fact_reviews.sql
WITH reviews AS (
    SELECT
        listing_id,
        id AS review_id,
        date,
        reviewer_id,
        reviewer_name,
        comments,
        comment_length
    FROM {{ ref('stg_reviews') }}
)

SELECT * FROM reviews
