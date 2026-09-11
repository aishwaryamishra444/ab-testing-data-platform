"""
Reads assignment3/logs/run_history.jsonl (written by pipeline_runner.py
after every run) and prints a health summary: recent run outcomes, success
rate, average duration, and whether the most recent run failed.

This is the "Monitoring" half of the rubric, kept separate from Logging:
logging answers "what happened inside one run, step by step" (for
debugging); monitoring answers "how has the pipeline been doing lately"
(for a human -- or a scheduled check -- to glance at without reading logs).

Usage:
    python monitor.py                  # human-readable summary
    python monitor.py --last 20        # look at more history
    python monitor.py --check          # exit 1 if the latest run failed
                                        # (wire this into cron as a second
                                        # job, or chain it after
                                        # pipeline_runner.py, for a
                                        # separate monitoring alert path)
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
RUN_HISTORY_PATH = HERE / "logs" / "run_history.jsonl"


def load_history():
    if not RUN_HISTORY_PATH.exists():
        return []
    with open(RUN_HISTORY_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--last", type=int, default=10, help="How many recent runs to show/consider")
    parser.add_argument("--check", action="store_true",
                         help="Exit 1 if the most recent run did not succeed (for chaining into alerting)")
    args = parser.parse_args()

    history = load_history()
    if not history:
        print("No runs recorded yet.")
        return 0

    recent = history[-args.last:]
    successes = [r for r in recent if r["status"] == "success"]

    print(f"Pipeline run history -- last {len(recent)} of {len(history)} total runs")
    print(f"{'Run ID':<28} {'Status':<26} {'Retries':<8} {'Duration':<10} Started")
    print("-" * 100)
    for r in recent:
        print(f"{r['run_id']:<28} {r['status']:<26} {r['retries_used']:<8} "
              f"{r['duration_seconds']:<10} {r['started_at']}")

    success_rate = len(successes) / len(recent) * 100
    avg_duration = sum(r["duration_seconds"] for r in successes) / len(successes) if successes else 0
    print("-" * 100)
    print(f"Success rate (last {len(recent)}): {success_rate:.0f}%   "
          f"Avg duration (successful runs): {avg_duration:.1f}s")

    latest = history[-1]
    if latest["status"] != "success":
        print(f"\n/!\\ Most recent run ({latest['run_id']}) did NOT succeed: "
              f"{latest['status']} -- {latest.get('error', '')}")
        if args.check:
            return 1
    else:
        print(f"\nMost recent run ({latest['run_id']}) succeeded.")

    if success_rate < 70 and len(recent) >= 5:
        print(f"/!\\ Success rate over last {len(recent)} runs is below 70% -- "
              f"investigate even if the most recent run passed.")
        if args.check:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
