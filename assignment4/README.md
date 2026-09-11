# Assignment 4 — Analytics Dashboard & Experiment Evaluation

Full technical documentation: [`00_documentation.md`](00_documentation.md)

## Deliverables vs Rubric

| Rubric item | Where it's covered |
|---|---|
| Dashboard (1 mark) | [`dashboard/dashboard.html`](dashboard/dashboard.html) — self-contained, interactive (Plotly), opens offline in any browser |
| KPI Computation (1 mark) | [`analysis/stats_analysis.py`](analysis/stats_analysis.py) + Documentation Section 1 |
| Statistical Analysis (1 mark) | SRM check, two-proportion z-tests, power recheck — Documentation Section 2 |
| Business Recommendations (1 mark) | Documentation Sections 3–4 (guardrail interpretation + final ship/hold recommendation) |
| Presentation (1 mark) | Dashboard's own visual polish + [`../docs/Assignment4_Executive_Summary.pdf`](../docs/Assignment4_Executive_Summary.pdf) (standalone 1-page summary) |

## How to Run

```bash
# 1. Compute statistics from the Assignment 2 warehouse
cd analysis
python stats_analysis.py --db ../../assignment2/db/ab_test.db

# 2. Export dashboard data (mart tables + stats results)
cd ../dashboard
python data_export.py --db ../../assignment2/db/ab_test.db

# 3. Build the dashboard
python build_dashboard.py
```

Then just double-click `dashboard/dashboard.html` — no server, no
internet connection required (Plotly.js is embedded inline).

## Headline Result

Onboarding completion rate rises significantly with every step-count
reduction (A→B: +15.6pp, A→C: +24.1pp, B→C: +8.5pp; all p < 0.0001,
no Sample Ratio Mismatch). But Arm C — the biggest winner on completion
— shows four guardrail regressions relative to control; Arm B shows
none at comparable magnitude. **Recommendation: ship Arm B, not Arm C.**
Full reasoning in Documentation Section 4.

## Repo Structure

```
assignment4/
├── 00_documentation.md        <- full write-up (KPI computation, statistical methodology, recommendation)
├── README.md                  <- you are here
├── analysis/
│   ├── stats_analysis.py      <- SRM check, z-tests, power recheck, recommendation synthesis
│   └── results.json           <- computed statistics (consumed by the dashboard)
├── dashboard/
│   ├── data_export.py         <- merges mart tables + results.json
│   ├── build_dashboard.py     <- renders the self-contained dashboard.html
│   ├── dashboard_data.json    <- merged data consumed by the dashboard
│   └── dashboard.html         <- the deliverable -- open this directly
└── evidence/                  <- dashboard screenshots embedded in the documentation
```

Full pipeline context: see the [repo root README](../README.md).
