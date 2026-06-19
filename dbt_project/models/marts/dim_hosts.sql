-- models/marts/dim_hosts.sql
WITH hosts AS (
    SELECT
        host_id,
        host_name,
        host_since,
        host_location,
        host_about,
        host_response_time,
        host_response_rate,
        host_acceptance_rate,
        host_is_superhost,
        host_neighbourhood,
        host_listings_count,
        host_total_listings_count,
        host_verifications,
        host_has_profile_pic,
        host_identity_verified,
        is_commercial_host,
        host_tenure_years
    FROM {{ ref('stg_listings') }}
)

SELECT DISTINCT * FROM hosts WHERE host_id IS NOT NULL
