-- ============================================================
-- DATA MART LAYER
-- Pre-aggregated, dashboard-ready tables — one row per
-- test_group (or per test_group x day), matching directly to the
-- KPIs and guardrails defined in the event tracking plan.
-- Built as tables (not views) so Assignment 4's dashboard can
-- query them cheaply without re-aggregating the fact table.
-- ============================================================

-- ---------------- MART: PRIMARY + SUPPORTING KPIs BY GROUP ----------------
DROP TABLE IF EXISTS mart_kpi_by_group;
CREATE TABLE mart_kpi_by_group AS
SELECT
    test_group,
    COUNT(*)                                                        AS users_started,
    SUM(completed_onboarding)                                       AS users_completed,
    ROUND(1.0 * SUM(completed_onboarding) / COUNT(*), 4)            AS onboarding_completion_rate,

    SUM(activated)                                                                          AS users_activated,
    ROUND(1.0 * SUM(activated) / NULLIF(SUM(completed_onboarding), 0), 4)                     AS activation_rate,

    SUM(purchased)                                                                          AS users_purchased,
    ROUND(1.0 * SUM(purchased) / NULLIF(SUM(activated), 0), 4)                                AS paid_conversion_rate,

    ROUND(AVG(time_to_first_lesson_seconds), 1)                                              AS avg_time_to_first_lesson_seconds,
    ROUND(1.0 * SUM(returned_day1) / NULLIF(SUM(completed_onboarding), 0), 4)                 AS day1_return_rate,
    ROUND(1.0 * SUM(returned_day7) / NULLIF(SUM(completed_onboarding), 0), 4)                 AS day7_return_rate,
    ROUND(1.0 * SUM(returned_day30) / NULLIF(SUM(completed_onboarding), 0), 4)                AS day30_return_rate
FROM fact_user_funnel
GROUP BY test_group
ORDER BY test_group;

-- ---------------- MART: GUARDRAIL METRICS BY GROUP ----------------
DROP TABLE IF EXISTS mart_guardrails_by_group;
CREATE TABLE mart_guardrails_by_group AS
SELECT
    test_group,
    ROUND(AVG(avg_relevance_score), 3)                                                       AS avg_lesson_relevance_score,
    ROUND(1.0 * SUM(refund_requested) / NULLIF(SUM(purchased), 0), 4)                         AS refund_rate,
    ROUND(1.0 * SUM(subscription_cancelled) / NULLIF(SUM(purchased), 0), 4)                   AS cancellation_rate,
    ROUND(1.0 * SUM(filed_support_ticket) / NULLIF(COUNT(*), 0), 4)                           AS support_ticket_rate,
    ROUND(1.0 * SUM(notif_accepted) / NULLIF(SUM(notif_shown), 0), 4)                         AS notification_optin_rate
FROM fact_user_funnel
GROUP BY test_group
ORDER BY test_group;

-- ---------------- MART: STEP-LEVEL DROP-OFF (funnel diagnostic) ----------------
DROP TABLE IF EXISTS mart_step_dropoff;
CREATE TABLE mart_step_dropoff AS
SELECT
    f.test_group,
    f.step_number,
    f.step_name,
    ds.step_bucket,
    COUNT(DISTINCT CASE WHEN f.step_event_type = 'onboarding_step_viewed' THEN f.user_id END)    AS users_viewed,
    COUNT(DISTINCT CASE WHEN f.step_event_type = 'onboarding_step_completed' THEN f.user_id END) AS users_completed,
    COUNT(DISTINCT CASE WHEN f.step_event_type = 'onboarding_step_abandoned' THEN f.user_id END) AS users_abandoned,
    ROUND(1.0 * COUNT(DISTINCT CASE WHEN f.step_event_type = 'onboarding_step_abandoned' THEN f.user_id END)
        / NULLIF(COUNT(DISTINCT CASE WHEN f.step_event_type = 'onboarding_step_viewed' THEN f.user_id END), 0), 4) AS step_abandon_rate
FROM fact_onboarding_step_events f
-- step_bucket lives on dim_step (design metadata, Section 2.3), not on the
-- fact rows themselves: only onboarding_step_viewed events carry step_bucket
-- in their raw properties (data_generator.py), so grouping by the fact
-- table's own step_bucket column would silently split each step into two
-- incomplete rows (one from _viewed, one from _completed/_abandoned).
-- Joining to dim_step gives one reliable bucket per (test_group, step_number).
JOIN dim_step ds ON ds.test_group = f.test_group AND ds.step_number = f.step_number
GROUP BY f.test_group, f.step_number, f.step_name, ds.step_bucket
ORDER BY f.test_group, f.step_number;

-- ---------------- MART: DAILY FUNNEL TREND ----------------
DROP TABLE IF EXISTS mart_daily_funnel;
CREATE TABLE mart_daily_funnel AS
SELECT
    install_date,
    test_group,
    COUNT(*)                                                    AS users_started,
    SUM(completed_onboarding)                                   AS users_completed,
    ROUND(1.0 * SUM(completed_onboarding) / COUNT(*), 4)        AS onboarding_completion_rate
FROM fact_user_funnel
GROUP BY install_date, test_group
ORDER BY install_date, test_group;

CREATE INDEX idx_mart_step_dropoff_group ON mart_step_dropoff(test_group);
CREATE INDEX idx_mart_daily_funnel_date ON mart_daily_funnel(install_date);
