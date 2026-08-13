"""
Ingests the Assignment 1 event CSV into SQLite and builds the
Raw -> Staging -> Warehouse -> Data Mart layers, then runs the
data quality checks and prints a report.

Usage:
    python build_db.py \
        --events-csv ../assignment1/generated_data/events.csv \
        --stepmap-json ../assignment1/stepmap.json \
        --db db/ab_test.db
"""
import argparse
import csv
import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent


def load_raw_events(con, csv_path, source_file):
    cur = con.cursor()
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = [
            (r["event_id"], r["user_id"], r["event_name"], r["event_timestamp"],
             r["test_group"], r["platform"], r["session_id"], r["properties"], source_file)
            for r in reader
        ]
    cur.executemany(
        """INSERT INTO raw_events
           (event_id, user_id, event_name, event_timestamp, test_group, platform, session_id, properties, _source_file)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    con.commit()
    return len(rows)


def load_dim_step(con, stepmap_path):
    with open(stepmap_path) as f:
        stepmap = json.load(f)

    cur = con.cursor()
    cur.execute("DROP TABLE IF EXISTS dim_step")
    cur.execute("""
        CREATE TABLE dim_step (
            test_group TEXT,
            step_number INTEGER,
            step_name TEXT,
            step_bucket TEXT
        )
    """)
    lookup = {s["step_name"]: s for s in stepmap["all_steps_master_list"]}
    rows = []
    for group, meta in stepmap["variants"].items():
        for pos, step_name in enumerate(meta["step_names"], start=1):
            rows.append((group, pos, step_name, lookup[step_name]["bucket"]))
    cur.executemany("INSERT INTO dim_step VALUES (?, ?, ?, ?)", rows)
    con.commit()
    return len(rows)


def inject_dirty_rows(con):
    """
    Inserts a handful of deliberately malformed rows straight into
    raw_events, mimicking real-world ingestion noise (a partial event
    from a flaky SDK, a duplicate delivery, a corrupted enum value).
    Lets the staging layer's validation/dedup logic be verified against
    something other than an already-clean dataset.
    """
    cur = con.cursor()
    dirty = [
        (None, "u_9999999", "onboarding_started", "2026-07-01T00:00:00", "A", "iOS", "s1", "{}", "dirty_injection"),
        ("bad_evt_1", None, "onboarding_started", "2026-07-01T00:00:00", "A", "iOS", "s1", "{}", "dirty_injection"),
        ("bad_evt_2", "u_9999998", None, "2026-07-01T00:00:00", "A", "iOS", "s1", "{}", "dirty_injection"),
        ("bad_evt_3", "u_9999997", "onboarding_started", None, "A", "iOS", "s1", "{}", "dirty_injection"),
        ("bad_evt_4", "u_9999996", "onboarding_started", "2026-07-01T00:00:00", "Z", "iOS", "s1", "{}", "dirty_injection"),
        ("bad_evt_5", "u_9999995", "onboarding_started", "2026-07-01T00:00:00", "A", "Windows", "s1", "{}", "dirty_injection"),
    ]
    cur.executemany(
        """INSERT INTO raw_events
           (event_id, user_id, event_name, event_timestamp, test_group, platform, session_id, properties, _source_file)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        dirty,
    )
    # duplicate delivery of a real event_id (picked after raw ingestion)
    cur.execute("""
        INSERT INTO raw_events (event_id, user_id, event_name, event_timestamp, test_group, platform, session_id, properties, _source_file)
        SELECT event_id, user_id, event_name, event_timestamp, test_group, platform, session_id, properties, 'dirty_injection_dup'
        FROM raw_events WHERE _source_file != 'dirty_injection' LIMIT 3
    """)
    con.commit()
    return len(dirty) + 3


def run_sql_file(con, path):
    with open(path) as f:
        script = f.read()
    con.executescript(script)
    con.commit()


def run_quality_checks(con, path):
    with open(path) as f:
        raw_statements = f.read().split(";")

    statements = []
    for raw in raw_statements:
        # drop comment-only lines, keep the actual SQL
        code_lines = [ln for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("--")]
        stmt = "\n".join(code_lines).strip()
        if stmt:
            statements.append(stmt)

    print("\n--- Data Quality Checks ---")
    results = []
    for stmt in statements:
        cur = con.execute(stmt)
        row = cur.fetchone()
        # row is (check_name, value)
        results.append(row)
        print(f"  {row[0]:<32} {row[1]}")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events-csv", default="../assignment1/generated_data/events.csv")
    parser.add_argument("--stepmap-json", default="../assignment1/stepmap.json")
    parser.add_argument("--db", default="db/ab_test.db")
    parser.add_argument("--inject-dirty-rows", action="store_true", default=True,
                         help="Insert a few malformed rows to exercise the validation/dedup logic (default: on)")
    args = parser.parse_args()

    db_path = HERE / args.db
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    con = sqlite3.connect(db_path)

    print("[1/5] Building raw layer schema...")
    run_sql_file(con, HERE / "schema/01_raw.sql")

    print("[2/5] Ingesting events CSV into raw_events...")
    n = load_raw_events(con, HERE / args.events_csv, Path(args.events_csv).name)
    print(f"      -> loaded {n} raw rows")

    if args.inject_dirty_rows:
        n_dirty = inject_dirty_rows(con)
        print(f"      -> injected {n_dirty} deliberately malformed rows to exercise staging validation")

    print("[3/5] Building staging layer...")
    run_sql_file(con, HERE / "schema/02_staging.sql")

    print("[4/5] Building warehouse layer (dims + facts)...")
    n_steps = load_dim_step(con, HERE / args.stepmap_json)
    print(f"      -> loaded {n_steps} dim_step rows")
    run_sql_file(con, HERE / "schema/03_warehouse.sql")

    print("[5/5] Building data mart layer...")
    run_sql_file(con, HERE / "schema/04_datamart.sql")

    run_quality_checks(con, HERE / "schema/05_data_quality_checks.sql")

    print("\n--- KPI Mart Preview ---")
    for row in con.execute("SELECT * FROM mart_kpi_by_group"):
        print(" ", row)

    print("\n--- Guardrail Mart Preview ---")
    for row in con.execute("SELECT * FROM mart_guardrails_by_group"):
        print(" ", row)

    con.close()
    print(f"\nDone. Database at {db_path}")


if __name__ == "__main__":
    main()
