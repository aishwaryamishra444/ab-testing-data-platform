-- ============================================================
-- WAREHOUSE LAYER
-- Dimensional (star-schema) model built on top of staging.
-- One conformed grain per fact table; dimensions are reusable
-- across facts and across future assignments (dashboards, etc.)
-- ============================================================

-- ---------------- DIM: USER ----------------
DROP TABLE IF EXISTS dim_user;
CREATE TABLE dim_user AS
SELECT
    user_id,
    test_group,
    platform,
    MIN(CASE WHEN event_name = 'app_installed' THEN event_timestamp END)   AS install_ts,
    MIN(CASE WHEN event_name = 'app_installed' THEN event_date END)        AS install_date,
    MAX(CASE WHEN event_name = 'account_created' THEN 1 ELSE 0 END)        AS account_created_flag,
    MAX(CASE WHEN event_name = 'account_created' THEN
        json_extract(properties, '$.signup_method') END)                  AS signup_method
FROM stg_events
GROUP BY user_id, test_group, platform;

CREATE UNIQUE INDEX idx_dim_user_user_id ON dim_user(user_id);

-- ---------------- DIM: DATE ----------------
DROP TABLE IF EXISTS dim_date;
CREATE TABLE dim_date AS
WITH RECURSIVE d(date_key) AS (
    SELECT MIN(event_date) FROM stg_events
    UNION ALL
    SELECT date(date_key, '+1 day') FROM d
    WHERE date_key < (SELECT MAX(event_date) FROM stg_events)
)
SELECT
    date_key,
    CAST(strftime('%Y', date_key) AS INTEGER)   AS year,
    CAST(strftime('%m', date_key) AS INTEGER)   AS month,
    CAST(strftime('%d', date_key) AS INTEGER)   AS day,
    CAST(strftime('%w', date_key) AS INTEGER)   AS day_of_week,
    CASE WHEN CAST(strftime('%w', date_key) AS INTEGER) IN (0, 6)
         THEN 1 ELSE 0 END                      AS is_weekend
FROM d;

CREATE UNIQUE INDEX idx_dim_date_key ON dim_date(date_key);

-- ---------------- DIM: STEP (per variant) ----------------
-- Loaded separately from stepmap.json by build_db.py (dim_step),
-- since the step->variant mapping is design metadata, not event data.

-- ---------------- FACT: STEP-LEVEL FUNNEL EVENTS (granular) ----------------
DROP TABLE IF EXISTS fact_onboarding_step_events;
CREATE TABLE fact_onboarding_step_events AS
SELECT
    event_id,
    user_id,
    test_group,
    platform,
    event_name                              AS step_event_type,   -- viewed / completed / abandoned
    CAST(step_number AS INTEGER)            AS step_number,
    step_name,
    step_bucket,
    time_on_step_seconds,
    exit_reason,
    event_timestamp,
    event_date
FROM stg_events
WHERE event_name IN ('onboarding_step_viewed', 'onboarding_step_completed', 'onboarding_step_abandoned');

CREATE INDEX idx_fact_step_events_user ON fact_onboarding_step_events(user_id);
CREATE INDEX idx_fact_step_events_group ON fact_onboarding_step_events(test_group);

-- ---------------- FACT: USER FUNNEL SUMMARY (one row per user) ----------------
-- This is the primary analytical fact: every KPI in the event
-- tracking plan can be derived from this table with a GROUP BY.
DROP TABLE IF EXISTS fact_user_funnel;
CREATE TABLE fact_user_funnel AS
SELECT
    u.user_id,
    u.test_group,
    u.platform,
    u.install_date,
    u.account_created_flag,

    MAX(CASE WHEN e.event_name = 'onboarding_started' THEN 1 ELSE 0 END)          AS started_onboarding,
    MAX(CASE WHEN e.event_name = 'onboarding_completed' THEN 1 ELSE 0 END)        AS completed_onboarding,
    MAX(CASE WHEN e.event_name = 'onboarding_completed' THEN
        CAST(json_extract(e.properties, '$.steps_completed') AS INTEGER) END)     AS steps_completed,
    MIN(CASE WHEN e.event_name = 'onboarding_started' THEN e.event_timestamp END) AS onboarding_started_ts,
    MIN(CASE WHEN e.event_name = 'onboarding_completed' THEN e.event_timestamp END) AS onboarding_completed_ts,

    MAX(CASE WHEN e.event_name = 'first_lesson_started' THEN 1 ELSE 0 END)        AS started_first_lesson,
    MAX(CASE WHEN e.event_name = 'first_lesson_completed' THEN 1 ELSE 0 END)      AS activated,
    MIN(CASE WHEN e.event_name = 'first_lesson_started' THEN e.event_timestamp END) AS first_lesson_started_ts,

    MAX(CASE WHEN e.event_name = 'app_opened_day1' THEN 1 ELSE 0 END)             AS returned_day1,
    MAX(CASE WHEN e.event_name = 'app_opened_day7' THEN 1 ELSE 0 END)             AS returned_day7,
    MAX(CASE WHEN e.event_name = 'app_opened_day30' THEN 1 ELSE 0 END)            AS returned_day30,

    MAX(CASE WHEN e.event_name = 'notification_permission_shown' THEN 1 ELSE 0 END)    AS notif_shown,
    MAX(CASE WHEN e.event_name = 'notification_permission_accepted' THEN 1 ELSE 0 END) AS notif_accepted,

    MAX(CASE WHEN e.event_name = 'trial_started' THEN 1 ELSE 0 END)               AS trial_started,
    MAX(CASE WHEN e.event_name = 'subscription_purchased' THEN 1 ELSE 0 END)      AS purchased,
    MAX(CASE WHEN e.event_name = 'subscription_purchased' THEN
        CAST(json_extract(e.properties, '$.price_usd') AS REAL) END)              AS price_usd,
    MAX(CASE WHEN e.event_name = 'refund_requested' THEN 1 ELSE 0 END)            AS refund_requested,
    MAX(CASE WHEN e.event_name = 'subscription_cancelled' THEN 1 ELSE 0 END)      AS subscription_cancelled,

    MAX(CASE WHEN e.event_name = 'support_ticket_created' THEN 1 ELSE 0 END)      AS filed_support_ticket,
    AVG(CASE WHEN e.event_name = 'lesson_feedback_submitted' THEN
        CAST(json_extract(e.properties, '$.relevance_score') AS REAL) END)        AS avg_relevance_score,

    CAST((julianday(MIN(CASE WHEN e.event_name = 'first_lesson_started' THEN e.event_timestamp END))
        - julianday(MIN(CASE WHEN e.event_name = 'onboarding_started' THEN e.event_timestamp END))) * 86400
        AS INTEGER)                                                               AS time_to_first_lesson_seconds

FROM dim_user u
LEFT JOIN stg_events e ON e.user_id = u.user_id
GROUP BY u.user_id, u.test_group, u.platform, u.install_date, u.account_created_flag;

CREATE UNIQUE INDEX idx_fact_user_funnel_user ON fact_user_funnel(user_id);
CREATE INDEX idx_fact_user_funnel_group ON fact_user_funnel(test_group);
