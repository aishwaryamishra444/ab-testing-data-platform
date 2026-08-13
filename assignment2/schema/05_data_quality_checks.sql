-- ============================================================
-- DATA QUALITY CHECKS
-- Run after each layer builds. Each SELECT should return 0 rows
-- (or 0 in the count) when the layer is healthy. build_db.py
-- executes these and reports failures rather than failing silently.
-- ============================================================

-- 1. Raw row count landed
SELECT 'raw_row_count' AS check_name, COUNT(*) AS value FROM raw_events;

-- 2. Rows rejected at staging (should be a small fraction of raw, not 0 —
--    proves the validation logic actually catches something)
SELECT 'staging_rejects' AS check_name, COUNT(*) AS value FROM stg_events_rejects;

-- 3. No duplicate event_id in staging
SELECT 'staging_duplicate_event_ids' AS check_name, COUNT(*) AS value
FROM (SELECT event_id FROM stg_events GROUP BY event_id HAVING COUNT(*) > 1);

-- 4. Every user in the warehouse has an app_installed event
SELECT 'users_missing_install_event' AS check_name, COUNT(*) AS value
FROM dim_user WHERE install_ts IS NULL;

-- 5. Referential integrity: every fact_user_funnel user_id exists in dim_user
SELECT 'orphan_fact_users' AS check_name, COUNT(*) AS value
FROM fact_user_funnel f
LEFT JOIN dim_user u ON u.user_id = f.user_id
WHERE u.user_id IS NULL;

-- 6. No user has completed_onboarding=1 without started_onboarding=1
SELECT 'completed_without_started' AS check_name, COUNT(*) AS value
FROM fact_user_funnel
WHERE completed_onboarding = 1 AND started_onboarding = 0;

-- 7. No user has activated=1 without completed_onboarding=1
SELECT 'activated_without_completed' AS check_name, COUNT(*) AS value
FROM fact_user_funnel
WHERE activated = 1 AND completed_onboarding = 0;

-- 8. No user has purchased=1 without activated=1
SELECT 'purchased_without_activated' AS check_name, COUNT(*) AS value
FROM fact_user_funnel
WHERE purchased = 1 AND activated = 0;

-- 9. test_group values are only A/B/C everywhere in the warehouse
SELECT 'invalid_test_group_values' AS check_name, COUNT(*) AS value
FROM fact_user_funnel WHERE test_group NOT IN ('A', 'B', 'C');

-- 10. Mart row counts match expected group cardinality (3 groups)
SELECT 'mart_kpi_group_count' AS check_name, COUNT(*) AS value FROM mart_kpi_by_group;

-- 11. No negative or absurd time-to-first-lesson values
SELECT 'negative_time_to_first_lesson' AS check_name, COUNT(*) AS value
FROM fact_user_funnel WHERE time_to_first_lesson_seconds < 0;

-- 12. Rates in the KPI mart are within [0, 1]
SELECT 'kpi_rates_out_of_bounds' AS check_name, COUNT(*) AS value
FROM mart_kpi_by_group
WHERE onboarding_completion_rate NOT BETWEEN 0 AND 1
   OR (activation_rate IS NOT NULL AND activation_rate NOT BETWEEN 0 AND 1)
   OR (paid_conversion_rate IS NOT NULL AND paid_conversion_rate NOT BETWEEN 0 AND 1);
