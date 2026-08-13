# Assignment 2 — Data Ingestion & Data Warehouse Modelling

Full technical documentation: [`00_documentation.md`](00_documentation.md)
(also rendered as a PDF at [`../docs/Assignment2_Documentation.pdf`](../docs/Assignment2_Documentation.pdf)).

## Deliverables vs Rubric

| Rubric item | Where it's covered |
|---|---|
| Database Design (2 marks) | Documentation Sections 2–3 (architecture + layer-by-layer design) + [`schema/`](schema/) |
| Data Ingestion (1 mark) | Documentation Section 4 + [`build_db.py`](build_db.py) `load_raw_events()` |
| SQL Transformations (1 mark) | [`schema/02_staging.sql`](schema/02_staging.sql), [`schema/03_warehouse.sql`](schema/03_warehouse.sql), [`schema/04_datamart.sql`](schema/04_datamart.sql) |
| Data Quality (1 mark) | Documentation Section 5 + [`schema/05_data_quality_checks.sql`](schema/05_data_quality_checks.sql) + dirty-row injection in `build_db.py` |

## How to Run

```bash
python build_db.py \
    --events-csv ../assignment1/generated_data/events.csv \
    --stepmap-json ../assignment1/stepmap.json \
    --db db/ab_test.db
```

Ingests the Assignment 1 CSV, injects a handful of deliberately malformed
rows to exercise the validation/dedup logic, builds all four layers in
order, and prints a data-quality report and KPI preview. See
[`00_documentation.md`](00_documentation.md) Section 6 for expected output.

## Rendering the PDF

```bash
python ../templates/build_pdf.py \
    --md 00_documentation.md \
    --title "Assignment 2: Data Ingestion & Data Warehouse Modelling" \
    --subtitle "Onboarding Flow Optimization A/B Test" \
    --out ../docs/Assignment2_Documentation.pdf
```

## Repo Structure

```
assignment2/
├── 00_documentation.md      <- full write-up (architecture, rationale, results)
├── README.md                <- you are here
├── build_db.py               <- ingestion + pipeline orchestrator
├── schema/
│   ├── 01_raw.sql
│   ├── 02_staging.sql
│   ├── 03_warehouse.sql
│   ├── 04_datamart.sql
│   └── 05_data_quality_checks.sql
└── db/                       <- ab_test.db built here (gitignored, regenerate locally)
```

Full pipeline context: see the [repo root README](../README.md).
