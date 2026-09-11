# Assignment 3 — Pipeline Automation & Data Validation

Full technical documentation: [`00_documentation.md`](00_documentation.md)

## Deliverables vs Rubric

| Rubric item | Where it's covered |
|---|---|
| Pipeline Automation (1 mark) | [`pipeline_runner.py`](pipeline_runner.py) — wraps Assignment 2's `build_db.py` with retry/validation/logging/alerting, no manual steps |
| Scheduling (1 mark) | [`scheduler/crontab.txt`](scheduler/crontab.txt) (real cron) + [`scheduler/scheduler_demo.py`](scheduler/scheduler_demo.py) (live-demo scheduler) — Documentation Section 7 |
| Validation (1 mark) | `VALIDATION_POLICY` in `pipeline_runner.py`, built on Assignment 2's `schema/05_data_quality_checks.sql` — Documentation Section 4 |
| Logging & Monitoring (1 mark) | Rotating log (`logs/pipeline.log`) — Documentation Section 3; [`monitor.py`](monitor.py) + `logs/run_history.jsonl` — Documentation Section 5 |
| Reliability (1 mark) | Error taxonomy (retry vs. alert), retry/backoff, and the full failure-scenario table — Documentation Sections 2 and 8 |

## How to Run

```bash
# Normal run (from a fresh clone, after Assignment 1 + 2 have produced
# assignment1/generated_data/events.csv and assignment2/db/ab_test.db at least once)
python pipeline_runner.py

# Check pipeline health
python monitor.py

# Watch the scheduler fire without waiting for the real schedule
python scheduler/scheduler_demo.py --demo-interval-seconds 15 --retry-delay-seconds 2
```

To see the retry/alert paths without waiting for a real failure, use the
built-in failure simulators — see Documentation Section 11 for the full
set of `--simulate` commands.

## Repo Structure

```
assignment3/
├── 00_documentation.md      <- full write-up (error taxonomy, design rationale, observed results)
├── README.md                <- you are here
├── pipeline_runner.py       <- orchestrator: retries, validation, logging, monitoring, alerting
├── notifier.py               <- pluggable alert channel (console/log by default; email/Slack stubs)
├── monitor.py                 <- run-history health summary + --check for chaining into alerting
├── scheduler/
│   ├── crontab.txt            <- real production cron entry + setup notes
│   └── scheduler_demo.py      <- pure-Python scheduler for demo / no-cron environments
└── logs/                      <- pipeline.log + run_history.jsonl written here at runtime (gitignored)
```

Full pipeline context: see the [repo root README](../README.md).
