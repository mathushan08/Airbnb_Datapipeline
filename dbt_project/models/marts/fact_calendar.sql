-- models/marts/fact_calendar.sql
WITH calendar AS (
    SELECT
        listing_id,
        date,
        available,
        price,
        adjusted_price,
        minimum_nights,
        maximum_nights,
        is_weekend,
        day_of_week,
        month,
        year
    FROM {{ ref('stg_calendar') }}
)

SELECT * FROM calendar
