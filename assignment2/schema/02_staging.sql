-- ============================================================
-- STAGING LAYER
-- Cleans and types the raw layer:
--   - de-duplicates on event_id
--   - drops rows failing basic validity checks (bad enum values,
--     null keys) into a rejects table instead of silently dropping
--   - casts event_timestamp to a real datetime
--   - flattens the most commonly-used JSON properties into typed
--     columns so downstream SQL doesn't need json_extract() everywhere
-- ============================================================

DROP TABLE IF EXISTS stg_events_rejects;
CREATE TABLE stg_events_rejects AS
SELECT *, 'null_or_invalid_key' AS reject_reason
FROM raw_events
WHERE event_id IS NULL
   OR user_id IS NULL
   OR event_name IS NULL
   OR event_timestamp IS NULL
   OR test_group NOT IN ('A', 'B', 'C')
   OR platform NOT IN ('iOS', 'Android');

DROP TABLE IF EXISTS stg_events;
CREATE TABLE stg_events AS
SELECT
    event_id,
    user_id,
    event_name,
    datetime(event_timestamp)                              AS event_timestamp,
    date(event_timestamp)                                   AS event_date,
    test_group,
    platform,
    session_id,
    properties,
    json_extract(properties, '$.step_number')               AS step_number,
    json_extract(properties, '$.step_name')                 AS step_name,
    json_extract(properties, '$.step_bucket')                AS step_bucket,
    json_extract(properties, '$.time_on_step_seconds')       AS time_on_step_seconds,
    json_extract(properties, '$.exit_reason')                AS exit_reason,
    json_extract(properties, '$.total_steps_in_flow')        AS total_steps_in_flow,
    json_extract(properties, '$.steps_completed')             AS steps_completed,
    json_extract(properties, '$.signup_method')               AS signup_method,
    json_extract(properties, '$.lesson_id')                   AS lesson_id,
    json_extract(properties, '$.score')                       AS lesson_score,
    json_extract(properties, '$.relevance_score')              AS relevance_score,
    json_extract(properties, '$.days_since_install')           AS days_since_install,
    json_extract(properties, '$.plan')                         AS subscription_plan,
    json_extract(properties, '$.price_usd')                    AS price_usd,
    json_extract(properties, '$.days_since_purchase')           AS days_since_purchase,
    json_extract(properties, '$.reason')                        AS refund_reason,
    json_extract(properties, '$.is_onboarding_related')          AS is_onboarding_related,
    json_extract(properties, '$.category')                       AS ticket_category
FROM (
    -- de-dup: keep one row per event_id (first ingested)
    SELECT r.*,
           ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY _ingested_at) AS rn
    FROM raw_events r
    WHERE event_id IS NOT NULL
      AND user_id IS NOT NULL
      AND event_name IS NOT NULL
      AND event_timestamp IS NOT NULL
      AND test_group IN ('A', 'B', 'C')
      AND platform IN ('iOS', 'Android')
) dedup
WHERE rn = 1;

CREATE INDEX idx_stg_events_user_id ON stg_events(user_id);
CREATE INDEX idx_stg_events_event_name ON stg_events(event_name);
CREATE INDEX idx_stg_events_test_group ON stg_events(test_group);
