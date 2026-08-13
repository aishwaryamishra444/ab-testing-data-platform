# Assignment 1 — Business Understanding, Event Design & Data Generation

## Deliverables

| File | Rubric item covered |
|---|---|
| [`01_business_understanding.md`](01_business_understanding.md) | Business Understanding (1 mark) |
| [`02_event_tracking_plan.md`](02_event_tracking_plan.md), [`event_schema.json`](event_schema.json), [`stepmap.json`](stepmap.json) | Event & Schema Design (2 marks) |
| [`data_generator.py`](data_generator.py), [`generated_data/events.csv`](generated_data/events.csv) | Realistic Data Generation (1 mark) |
| This README + linked docs | Documentation (1 mark) |

## How the data was generated

```bash
python data_generator.py --n-users 6000 --seed 42 --out generated_data/events.csv
```

Produces one row per event (long format) matching `event_schema.json`, for
6,000 simulated users split evenly across variants A/B/C, stratified so
iOS/Android are balanced within each group.

### Sanity-checked funnel numbers from the generated dataset

| Metric | A (13 steps) | B (7 steps) | C (5 steps) |
|---|---|---|---|
| Onboarding completion rate | ~57% | ~73% | ~82% |
| Activation rate (of completers) | ~70% | ~63% | ~66% |
| Paid conversion (of activated) | ~6% | ~6% | ~6% |
| Day-30 return (of completers, guardrail) | ~36% | ~34% | ~29% |
| Support tickets (of starters, guardrail) | ~0.9% | ~1.2% | ~2.2% |
| Notification opt-in (guardrail) | ~53% | ~51% | ~33% |

This mirrors the business document: completion rate improves as steps drop,
paid conversion stays flat (confirming the checkout funnel itself isn't the
problem), and the guardrails show real, measurable trade-offs for the
shortest flow (C) — exactly the tension the experiment is designed to surface
in Assignment 4's analysis.

## Rendering the PDF

The full documentation (business understanding + event tracking plan) is
built into a single styled PDF via the shared pipeline in `../templates/`:

```bash
python ../templates/build_pdf.py \
    --md 01_business_understanding.md 02_event_tracking_plan.md \
    --title "Assignment 1: Business Understanding, Event Design & Data Generation" \
    --subtitle "Onboarding Flow Optimization A/B Test" \
    --out ../docs/Assignment1_Documentation.pdf
```

## Full pipeline

This assignment is step 1 of 4. See the [repo root README](../README.md) for
the full pipeline (Assignment 2: ingestion + warehouse modelling,
Assignment 3: automation + validation, Assignment 4: dashboard + analysis).
