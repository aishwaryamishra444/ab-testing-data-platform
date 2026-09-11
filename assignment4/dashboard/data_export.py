"""
Pulls everything the dashboard needs -- KPI/guardrail marts, step
drop-off, daily trend, and the statistical test results from
stats_analysis.py -- into a single dashboard_data.json, so the dashboard
itself is a static HTML file with no live database dependency.

Usage:
    python dashboard/data_export.py --db ../assignment2/db/ab_test.db
"""
import argparse
import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent


def fetch_all(con, sql):
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="../assignment2/db/ab_test.db")
    parser.add_argument("--stats-json", default="../analysis/results.json")
    parser.add_argument("--out", default="dashboard_data.json")
    args = parser.parse_args()

    con = sqlite3.connect(HERE / args.db)

    data = {
        "kpi_by_group": fetch_all(con, "SELECT * FROM mart_kpi_by_group ORDER BY test_group"),
        "guardrails_by_group": fetch_all(con, "SELECT * FROM mart_guardrails_by_group ORDER BY test_group"),
        "step_dropoff": fetch_all(con, "SELECT * FROM mart_step_dropoff ORDER BY test_group, step_number"),
        "daily_funnel": fetch_all(con, "SELECT * FROM mart_daily_funnel ORDER BY install_date, test_group"),
    }

    with open(HERE / args.stats_json) as f:
        data["stats"] = json.load(f)

    out_path = HERE / args.out
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {out_path}")
    for k, v in data.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)} rows")
    con.close()


if __name__ == "__main__":
    main()
