---
title: "Assignment 1 — Business Understanding, Event Design & Data Generation"
subtitle: "Onboarding Flow Optimization A/B Test — Data Engineering Weekly Assignments"
author: "Aishwarya Mishra"
date: "August 2026"
---

# 1. Business Understanding

## 1.1 The Business

A B2C mobile app that teaches English using AI. New users go through an onboarding
flow (account creation, level assessment, goal setting, personalization questions,
notification permission, etc.) before they reach the actual product.

## 1.2 The Problem

The current onboarding flow has **13 sequential steps**. Only **60% of users who
start onboarding finish it**, against an industry benchmark of **~80%**. Every
extra step is a point where a new user can quit before ever experiencing the
product — and since most of these users were already paid for via acquisition
spend (ads, referrals), every drop-off is wasted spend.

Critically, the **post-onboarding paid conversion rate (6%) is already healthy
and in line with industry**. The bottleneck is not the product or the price —
it is the number of people who never make it far enough to be counted.

## 1.3 The Opportunity (Illustrative)

Using illustrative figures of 100,000 new users/month and $30 average monthly
revenue per paying user:

| Scenario | Completion Rate | Users who Finish | Paying Users (6%) | Monthly Revenue |
|---|---|---|---|---|
| Current (13 steps) | 60% | 60,000 | 3,600 | $108,000 |
| Target (industry) | 80% | 80,000 | 4,800 | $144,000 |

Closing the gap is worth an estimated **+$36,000/month (+$432,000/year)** —
from the *same* user base, with zero additional acquisition spend.

## 1.4 Hypothesis

Reducing the number of onboarding steps from 13 will reduce drop-off, increasing
onboarding completion, activation, and downstream paid conversion. The design
also isolates *step count* from *step content* — steps are trimmed by removing
or deferring genuinely low-value steps (see 1.6), not just truncating the flow,
so a win can be attributed to friction reduction rather than to accidentally
dropping a specific confusing step.

## 1.5 Experiment Design

| | A — Control | B — Medium | C — Short |
|---|---|---|---|
| Steps | 13 (unchanged) | 7 | 5 |
| Traffic split | ~33% | ~33% | ~33% |
| Platform | iOS + Android, balanced | iOS + Android, balanced | iOS + Android, balanced |
| Randomization unit | Per new user, at first app open | | |

## 1.6 How Steps Are Cut

Steps are bucketed as **Must-have** (account creation, level check — needed
before personalization is possible), **Can-wait** (notification permission,
detailed goals — deferred to after first value), and **Nice-to-have /
combinable** (merged into other screens or dropped). B keeps must-have +
some can-wait steps; C keeps only must-have steps.

# 2. KPIs

## 2.1 Primary Metric

- **Onboarding completion rate** — % of users who start onboarding and finish
  it. This is the headline number: it directly measures whether shorter
  onboarding reduces quitting.

## 2.2 Supporting Metrics

| Metric | Definition | Purpose |
|---|---|---|
| Activation rate | % of starters who finish onboarding **and** complete their first lesson | Confirms people are engaging, not just clicking through faster |
| Day-1 / Day-7 return rate | % of users who reopen the app 1 / 7 days later | Confirms retained interest, not just a rushed completion |
| Paid conversion rate | % of activated users who become paying subscribers | Ties the funnel directly to revenue |
| Time to first lesson | Time from onboarding start to first real lesson | Direct measure of friction removed |

## 2.3 Guardrail Metrics (must not regress)

| Guardrail | Risk if ignored |
|---|---|
| Lesson relevance / personalization quality | Fewer onboarding questions → generic content → quiet churn |
| Day-30 return rate | Shorter onboarding could attract low-intent users who finish easily but never stick |
| Refund / cancellation rate | Rushed onboarding → users don't understand what they signed up for |
| Onboarding-related support tickets | A skipped step (e.g. billing/permissions explanation) creates confusion |
| Notification opt-in rate | If deferred/removed, hurts our ability to re-engage users later |

# 3. Data Platform Requirement

Answering "did the new onboarding work, and is it safe to ship" requires a
pipeline that can: (1) collect every funnel and product event at the user
level, tagged with test group/platform/timestamp; (2) validate and land it
reliably; (3) model it into a warehouse that supports both the primary metric
and every guardrail; and (4) serve it to a dashboard and a statistical test.
Assignments 1–4 build exactly this pipeline, end to end.

See [`02_event_tracking_plan.md`](02_event_tracking_plan.md) for the full event
schema and [`data_generator.py`](data_generator.py) for the synthetic data used
to develop and test the pipeline before real production data is available.
