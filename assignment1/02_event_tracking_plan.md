---
title: "Event Tracking Plan, Schema Design & Data Governance"
subtitle: "Assignment 1 — Onboarding Flow Optimization A/B Test"
author: "Aishwarya Mishra | USN 2648610 | MSc Computational Statistics & Applied AI, Christ University"
---

## Abstract

This document specifies the event-level instrumentation required to
operationalize the KPI framework defined in
[`01_business_understanding.md`](01_business_understanding.md). It defines
a schema, a naming taxonomy, per-event validation rules, randomization and
identity semantics, a versioning strategy, and the explicit lineage from
raw events to each KPI and guardrail. The schema is implemented in
machine-readable form as [`event_schema.json`](event_schema.json) and
[`stepmap.json`](stepmap.json), which are consumed directly — not merely
referenced — by the data generator, the warehouse build in Assignment 2,
and (prospectively) the dashboard in Assignment 4, so this document and the
running system cannot silently drift apart.

## 1. Design Principles

1. **Long (narrow) format.** One row per event, not one row per user with
   dozens of event-specific columns. This trades some query-time
   convenience (addressed by the warehouse layer in Assignment 2) for
   schema flexibility: a new event type is a new value in `event_name`, not
   a schema migration.
2. **Uniform envelope, variable payload.** Every event shares seven
   identical top-level fields (Section 2) regardless of type; type-specific
   detail is isolated in a `properties` object. This keeps the raw table
   narrow and lets generic tooling (deduplication, PII scanning, routing)
   operate without per-event-type branching.
3. **Deterministic naming taxonomy.** Every event name follows
   `object_verb_pasttense` in `snake_case` (e.g., `onboarding_step_completed`,
   not `CompleteStep` or `step-complete`). Past tense signals that the event
   is an immutable fact about something that already happened, not a
   command or a mutable state.
4. **Idempotent identity.** Every event carries a client-generated
   `event_id` (UUIDv4) at creation time, independent of when or how many
   times it is delivered to the backend. This is what allows the staging
   layer (Assignment 2) to de-duplicate retried deliveries safely.
5. **No event without an owning user and timestamp.** `user_id` and
   `event_timestamp` are non-nullable by contract; violations are routed to
   a quarantine table rather than silently dropped or silently accepted
   (Assignment 2, Section on Data Quality).

## 2. Envelope Specification

| Field | Type | Nullable | Description |
|---|---|---|---|
| `event_id` | string (UUIDv4) | No | Client-generated unique identifier; the basis for deduplication |
| `user_id` | string | No | Pseudonymous identifier, stable for the user's lifetime in the dataset |
| `event_name` | string (enum) | No | One of the catalog names in Section 5 |
| `event_timestamp` | string (ISO-8601, UTC) | No | Client-side event time, not server ingestion time |
| `test_group` | string (enum: `A`, `B`, `C`) | No | Assigned onboarding arm; set once per user at randomization and copied onto every subsequent event for that user |
| `platform` | string (enum: `iOS`, `Android`) | No | Device platform |
| `session_id` | string | Yes | Groups events emitted within one continuous app session |
| `properties` | object (JSON) | Yes | Event-specific attributes; schema per `event_name` given in Section 5 |

`test_group` and `platform` are denormalized onto every event, not only onto
a separate assignment record, deliberately: it allows any single event-level
query (e.g., a step-abandonment funnel) to be sliced by arm without a join
back to a user dimension, at the cost of redundant storage — a standard
trade-off for high-cardinality, append-only event streams.

## 3. Identity, Randomization, and Assignment Integrity

- `user_id` is minted at `app_installed` and is treated as immutable for the
  remainder of the user's event history in this dataset. No identity-merge
  or cross-device-stitching logic is in scope.
- Arm assignment happens exactly once, at `onboarding_started` (functionally
  the user's first app open), via a uniform random draw across `{A, B, C}`,
  stratified so that iOS and Android are balanced within each arm. Once
  assigned, `test_group` does not change for that user, including on
  reinstall (reinstall handling is out of scope for this dataset; each
  simulated user installs exactly once).
- **Sample Ratio Mismatch (SRM) as a pre-condition, not an afterthought.**
  Because every event carries `test_group`, an SRM check —
  `COUNT(DISTINCT user_id)` per arm compared against the expected 33/33/33
  split — is a single `GROUP BY` against `mart_kpi_by_group`
  (Assignment 2) and is treated as a precondition for interpreting *any*
  other metric in Assignment 4: a broken randomizer invalidates every
  downstream comparison regardless of how favorable the primary metric
  looks.

## 4. Data Governance and Privacy Posture

- `user_id` is pseudonymous by construction (a generated identifier, not an
  email address, device advertising ID, or other directly identifying
  value), consistent with data-minimization practice for experimentation
  telemetry.
- No event in the catalog (Section 5) captures free-text user input beyond
  `refund_reason` and `exit_reason`, both of which are constrained to a
  fixed enumeration rather than free text, to avoid inadvertently
  collecting PII inside an analytics payload.
- `support_ticket_created` intentionally captures only a boolean
  relevance flag and a coarse `category` enum, not ticket contents; ticket
  contents live in the support system of record, not the analytics event
  stream.
- Retention policy (for a production deployment, out of scope for this
  academic dataset): raw event-level data would typically be retained for
  the duration of the experiment plus one full guardrail observation window
  (30 days post-experiment-close per Section 3.4 of the business-
  understanding document), after which only the aggregated data-mart tables
  would be retained.

## 5. Event Catalog

Each entry below states the triggering condition and its `properties`
schema. The complete machine-readable form (used directly by
`data_generator.py`) is [`event_schema.json`](event_schema.json).

### 5.1 Funnel and Onboarding Events

| Event | Triggering Condition | `properties` |
|---|---|---|
| `app_installed` | App installed on device | `device_platform` |
| `onboarding_started` | User begins onboarding (arm assignment occurs here) | `total_steps_in_flow` |
| `onboarding_step_viewed` | Step rendered to the user | `step_number`, `step_name`, `step_bucket` |
| `onboarding_step_completed` | User successfully submits/advances past a step | `step_number`, `step_name`, `time_on_step_seconds` |
| `onboarding_step_abandoned` | User exits the app or session mid-step | `step_number`, `step_name`, `exit_reason` (enum: `closed_app`, `backgrounded`, `timeout`, `unknown`) |
| `onboarding_completed` | User reaches the end of their arm's step sequence | `total_time_seconds`, `steps_completed` |
| `account_created` | Account/profile persisted | `signup_method` (enum: `email`, `google`, `apple`) |

### 5.2 Product Engagement Events

| Event | Triggering Condition | `properties` |
|---|---|---|
| `first_lesson_started` | User begins their first lesson (activation trigger) | `lesson_id` |
| `first_lesson_completed` | User finishes their first lesson (activation success event) | `lesson_id`, `score` |
| `app_opened_day1` / `app_opened_day7` / `app_opened_day30` | Return visit at the corresponding horizon | `days_since_install` |
| `notification_permission_shown` | OS-level permission prompt displayed | — |
| `notification_permission_accepted` / `notification_permission_denied` | User responds to the prompt | — |

### 5.3 Monetization Events

| Event | Triggering Condition | `properties` |
|---|---|---|
| `trial_started` | Free trial begins | `trial_length_days` |
| `subscription_purchased` | User converts to a paying subscriber | `plan` (enum: `monthly`, `annual`), `price_usd` |
| `subscription_cancelled` | User cancels an active subscription | `days_since_purchase` |
| `refund_requested` | User requests a refund | `days_since_purchase`, `reason` (enum: `not_as_expected`, `too_expensive`, `found_free_alternative`, `other`) |

### 5.4 Quality and Guardrail Events

| Event | Triggering Condition | `properties` |
|---|---|---|
| `app_crash` / `app_error` | Technical fault during a session | `error_code`, `screen` |
| `support_ticket_created` | Support ticket logged (may originate in support tooling, not the app) | `is_onboarding_related` (boolean), `category` (enum) |
| `lesson_feedback_submitted` | User rates lesson relevance | `relevance_score` (integer, 1-5) |

## 6. Per-Event Validation Rules

Applied at the staging layer (Assignment 2, `schema/02_staging.sql`); listed
here as part of the schema contract rather than buried in SQL comments:

| Rule | Applies To | Rejection Behavior |
|---|---|---|
| `event_id`, `user_id`, `event_name`, `event_timestamp` non-null | All events | Routed to `stg_events_rejects`, not dropped |
| `test_group` in `{A, B, C}` | All events | Routed to `stg_events_rejects` |
| `platform` in `{iOS, Android}` | All events | Routed to `stg_events_rejects` |
| `event_id` uniqueness | All events | First-seen row wins; subsequent duplicates dropped at staging |
| `step_number` present and in `{1..13}` | `onboarding_step_*` events | Enforced by construction in the generator; would be a staging check against a production source |
| `relevance_score` in `{1..5}` | `lesson_feedback_submitted` | Enforced by construction; production staging would range-check |

## 7. Schema Versioning and Evolution

The schema is expressed as data (`event_schema.json`), not as inline logic,
specifically so it can be versioned independently of the code that produces
or consumes it. The evolution policy assumed for this project:

- **Additive changes** (a new event name, a new optional `properties` key)
  are non-breaking and require no coordination beyond updating
  `event_schema.json`.
- **Breaking changes** (renaming an event, changing a field's type, making
  an optional field required) would require a new `event_name` or a
  `schema_version` envelope field in a production system; this dataset does
  not exercise that path, since it is generated once against a single fixed
  schema version.
- The step-to-bucket-to-arm mapping (`stepmap.json`) is versioned
  separately from the event schema itself, because it is experiment-design
  metadata (which steps exist, and which arm sees them) rather than
  wire-format metadata (what an event looks like on the wire) — conflating
  the two would make it harder to run a second, differently-designed
  experiment against the same event schema in the future.

## 8. Metric-to-Event Lineage

Restated here from the business-understanding document, in the direction
that matters for instrumentation review: for each KPI, the minimal set of
events that must be reliably captured for the metric to be computable.

| KPI | Required Events |
|---|---|
| Onboarding completion rate | `onboarding_started`, `onboarding_completed` |
| Activation rate | `onboarding_completed`, `first_lesson_completed` |
| Day-1 / Day-7 / Day-30 return rate | `onboarding_completed` (denominator), `app_opened_day1`/`day7`/`day30` |
| Paid conversion rate | `first_lesson_completed`, `subscription_purchased` |
| Time to first lesson | `onboarding_started`, `first_lesson_started` |
| Lesson relevance (guardrail) | `lesson_feedback_submitted` |
| Refund / cancellation rate (guardrail) | `subscription_purchased`, `refund_requested`, `subscription_cancelled` |
| Notification opt-in rate (guardrail) | `notification_permission_shown`, `notification_permission_accepted` |
| Onboarding support-ticket rate (guardrail) | `onboarding_started`, `support_ticket_created` |

Any gap in this table — an event type dropped from instrumentation — is, by
construction, a gap in the organization's ability to answer the business
question in Section 1 of the business-understanding document. This table is
therefore the acceptance criterion for "is the platform instrumented
correctly," independent of whatever the experiment's eventual result turns
out to be.

See [`event_schema.json`](event_schema.json) for the machine-readable
schema, [`stepmap.json`](stepmap.json) for the per-arm step definitions, and
[`data_generator.py`](data_generator.py) for the synthetic dataset that
implements this specification end to end.
