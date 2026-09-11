---
title: "Executive Summary"
subtitle: "Onboarding Flow Optimization A/B Test — Assignment 4"
author: "Aishwarya Mishra | USN 2648610 | MSc Computational Statistics & Applied AI, Christ University"
---

## The Question

The current 13-step onboarding flow completes at 60%, against an ~80%
industry benchmark. We tested two shorter alternatives — **B (7 steps)**
and **C (5 steps)** — against the current flow (**A, control**) to find
out whether cutting steps closes that gap, and what it costs.

## The Headline Result

**Completion rate rises significantly at every step reduction.**

| Arm | Steps | Completion Rate | vs. Control |
|---|---|---|---|
| A — Control | 13 | 57.4% | — |
| B — Medium | 7 | 73.0% | **+15.6 pp**, p < 0.0001 |
| C — Short | 5 | 81.5% | **+24.1 pp**, p < 0.0001 |

No Sample Ratio Mismatch was detected (allocation was exactly 2,000 /
2,000 / 2,000 as designed), and the sample is well-powered — every
observed difference is far above the 4.3-percentage-point minimum this
sample size could reliably detect.

## But It's Not a Clean Win for C

Arm C wins the most on completion — but it also shows measurable
regressions the control doesn't, on exactly the guardrails this
experiment was designed to watch:

| Guardrail | A (Control) | C (Short) |
|---|---|---|
| Lesson relevance score | 3.98 / 5 | 3.44 / 5 |
| Support-ticket rate | 0.9% | 2.2% |
| Notification opt-in rate | 52.8% | 32.7% |
| Day-30 return rate | 36.2% | 29.0% |

**Arm B shows none of these regressions at comparable magnitude.**
Paid conversion rate, meanwhile, stays flat across all three arms
(~6%) — confirming the checkout funnel itself was never the problem.

## Recommendation

> ### Ship Arm B. Hold Arm C for a follow-up experiment.

B captures most of the completion-rate opportunity (+15.6pp, ~890
additional paying users/month at illustrative volume) without the
guardrail cost C carries. C should be revisited as a narrower experiment
investigating whether its additional step cuts can be made without the
personalization and retention trade-offs observed here.

*Full statistical methodology, all pairwise tests, and complete guardrail
analysis: see `00_documentation.md` and the interactive dashboard
(`dashboard/dashboard.html`).*
