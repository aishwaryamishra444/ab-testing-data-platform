---
title: "Event Tracking Plan & Event Schema"
subtitle: "Onboarding Flow Optimization A/B Test"
author: "Aishwarya Mishra"
date: "August 2026"
---

# 1. Design Principles

1. **One row per event** (long/narrow format) — flexible for any funnel shape,
   easy to append new event types without a schema migration.
2. **Every event carries the same envelope fields** so any event can be sliced
   by test group, platform, user and time without joins.
3. **Event-specific detail lives in a `properties` JSON blob** rather than
   dozens of mostly-null columns — kept narrow at the raw layer, flattened out
   later in staging/warehouse.
4. Event names are `snake_case`, past-tense, `object_verb` (e.g.
   `onboarding_step_completed`) for consistency and easy grouping.

# 2. Envelope (present on every event)

| Field | Type | Description |
|---|---|---|
| `event_id` | UUID (string) | Unique id per event row |
| `user_id` | string | Anonymous/user identifier, stable per user |
| `event_name` | string | One of the catalog names in Section 4 |
| `event_timestamp` | ISO-8601 datetime (UTC) | When the event occurred |
| `test_group` | enum `A`,`B`,`C` | Assigned onboarding variant |
| `platform` | enum `iOS`,`Android` | Device platform |
| `session_id` | string | Groups events within one app session |
| `properties` | JSON | Event-specific attributes (Section 4) |

# 3. Identity & Randomization

- `user_id` is assigned at `app_installed` and is stable for the user's
  lifetime in the dataset.
- Test-group assignment happens once, at `onboarding_started` (first app
  open), via a uniform random draw across A/B/C (~33% each), stratified so
  iOS/Android are balanced within each group.

# 4. Event Catalog

## 4.1 Funnel & Onboarding Events

| Event | Fires when | Key `properties` |
|---|---|---|
| `app_installed` | User installs the app | `device_platform` |
| `onboarding_started` | User begins onboarding | `total_steps_in_flow` |
| `onboarding_step_viewed` | User sees a step | `step_number`, `step_name`, `step_bucket` (must_have/can_wait/nice_to_have) |
| `onboarding_step_completed` | User completes a step | `step_number`, `step_name`, `time_on_step_seconds` |
| `onboarding_step_abandoned` | User exits mid-step | `step_number`, `step_name`, `exit_reason` |
| `onboarding_completed` | User finishes the whole flow | `total_time_seconds`, `steps_completed` |
| `account_created` | User creates an account/profile | `signup_method` |

## 4.2 Product Engagement Events

| Event | Fires when | Key `properties` |
|---|---|---|
| `first_lesson_started` | User begins first lesson (activation trigger) | `lesson_id` |
| `first_lesson_completed` | User finishes first lesson (activation success) | `lesson_id`, `score` |
| `app_opened_day1` / `app_opened_day7` / `app_opened_day30` | Return visit at that horizon | `days_since_install` |
| `notification_permission_shown` | Permission prompt shown | — |
| `notification_permission_accepted` / `notification_permission_denied` | User responds | — |

## 4.3 Monetization Events

| Event | Fires when | Key `properties` |
|---|---|---|
| `trial_started` | Free trial begins | `trial_length_days` |
| `subscription_purchased` | User converts to paying subscriber | `plan`, `price_usd` |
| `subscription_cancelled` | User cancels | `days_since_purchase` |
| `refund_requested` | User requests refund | `days_since_purchase`, `reason` |

## 4.4 Quality & Guardrail Events

| Event | Fires when | Key `properties` |
|---|---|---|
| `app_crash` / `app_error` | Technical issue | `error_code`, `screen` |
| `support_ticket_created` | Support ticket logged | `is_onboarding_related` (bool), `category` |
| `lesson_feedback_submitted` | In-app lesson rating | `relevance_score` (1-5) |

# 5. Step Maps by Variant

Encodes the "Must-have / Can-wait / Nice-to-have" bucketing from the business
document, used both by the generator and by the warehouse to explain *why*
completion differs between groups.

| Variant | Steps | Composition |
|---|---|---|
| A (control) | 13 | All must-have + can-wait + nice-to-have steps |
| B (medium) | 7 | All must-have + a subset of can-wait steps |
| C (short) | 5 | Must-have steps only |

Full step list with bucket labels: `stepmap.json`.

# 6. Metric → Event Lineage

| KPI | Computed from |
|---|---|
| Onboarding completion rate | `onboarding_started` vs `onboarding_completed` |
| Activation rate | `onboarding_completed` vs `first_lesson_completed` |
| Day-1 / Day-7 / Day-30 return rate | `app_opened_day1/7/30` vs `onboarding_started` |
| Paid conversion rate | `first_lesson_completed` vs `subscription_purchased` |
| Time to first lesson | `onboarding_started.timestamp` → `first_lesson_started.timestamp` |
| Refund / cancellation rate | `subscription_purchased` vs `refund_requested`/`subscription_cancelled` |
| Notification opt-in rate | `notification_permission_shown` vs `_accepted` |
| Support ticket rate (onboarding) | `support_ticket_created` where `is_onboarding_related` |

See [`event_schema.json`](event_schema.json) for the machine-readable schema
and [`stepmap.json`](stepmap.json) for the per-variant step definitions, both
consumed directly by [`data_generator.py`](data_generator.py).
