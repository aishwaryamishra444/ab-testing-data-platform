"""
A Python-native scheduler for environments where installing a real cron
job isn't practical (a grader's machine, a container, CI) or where you
want to watch a scheduled run actually fire during a demo instead of
waiting until 2am. crontab.txt in this same folder is the real production
answer; this is the same schedule expressed in a way you can run and see
work in the same terminal session.

Usage:
    python scheduler_demo.py                        # daily at 02:00, real schedule
    python scheduler_demo.py --demo-interval-seconds 15   # fire every 15s, for live demo
    python scheduler_demo.py --run-once              # run the job immediately once, then exit
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

import schedule

HERE = Path(__file__).parent
RUNNER = (HERE / ".." / "pipeline_runner.py").resolve()


def run_pipeline_job(extra_args):
    print(f"\n[scheduler] Firing pipeline_runner.py at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    result = subprocess.run([sys.executable, str(RUNNER), *extra_args])
    if result.returncode != 0:
        print(f"[scheduler] Job exited non-zero ({result.returncode}) -- pipeline_runner.py's own "
              f"Notifier already fired for this; the scheduler doesn't double-alert.")
    return result.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--daily-at", default="02:00", help="Real schedule: HH:MM 24h, default 02:00")
    parser.add_argument("--demo-interval-seconds", type=int, default=None,
                         help="If set, ignore --daily-at and fire this often instead, for a live demo")
    parser.add_argument("--run-once", action="store_true", help="Run the job immediately once, then exit")
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--retry-delay-seconds", type=float, default=300)
    args = parser.parse_args()

    extra_args = ["--max-retries", str(args.max_retries), "--retry-delay-seconds", str(args.retry_delay_seconds)]

    if args.run_once:
        sys.exit(run_pipeline_job(extra_args))

    if args.demo_interval_seconds:
        print(f"[scheduler] DEMO MODE: running every {args.demo_interval_seconds}s (Ctrl+C to stop)")
        schedule.every(args.demo_interval_seconds).seconds.do(run_pipeline_job, extra_args)
    else:
        print(f"[scheduler] Scheduled daily at {args.daily_at} (Ctrl+C to stop)")
        schedule.every().day.at(args.daily_at).do(run_pipeline_job, extra_args)

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[scheduler] Stopped.")


if __name__ == "__main__":
    main()
