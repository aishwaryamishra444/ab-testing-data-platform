"""
Pipeline automation orchestrator for the Assignment 2 ingestion/warehouse
build. Wraps that pipeline with retry logic, structured logging, a
post-build validation policy, run-history monitoring, and failure
alerting -- the four things Assignment 3 asks for on top of Assignment 2's
already-working SQL.

Design summary (full rationale in 00_documentation.md):
  - Errors are classified as TRANSIENT (retry with backoff -- e.g. a
    locked database, a simulated connection blip) or FATAL (alert
    immediately, do not retry -- e.g. missing source file, corrupt schema
    config, or a data-quality policy violation, since re-running the same
    bad input produces the same bad output).
  - Every run is logged to a rotating file (assignment3/logs/pipeline.log)
    and console, and its outcome is appended to a monitoring history file
    (assignment3/logs/run_history.jsonl) that monitor.py summarizes.
  - On final failure (retries exhausted, or any fatal error), a Notifier
    is invoked -- console/log by default, pluggable to email/Slack.

Usage:
    python pipeline_runner.py                     # normal run
    python pipeline_runner.py --simulate transient-then-ok
    python pipeline_runner.py --simulate always-transient
    python pipeline_runner.py --simulate fatal-missing-file
    python pipeline_runner.py --simulate bad-data
"""
import argparse
import json
import logging
import logging.handlers
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
ASSIGNMENT2 = (HERE / ".." / "assignment2").resolve()
sys.path.insert(0, str(ASSIGNMENT2))

import build_db  # noqa: E402  (assignment2/build_db.py -- reused, not duplicated)

from notifier import LogNotifier  # noqa: E402

LOG_DIR = HERE / "logs"
RUN_HISTORY_PATH = LOG_DIR / "run_history.jsonl"


# --------------------------------------------------------------------------
# Error taxonomy
# --------------------------------------------------------------------------
class TransientError(Exception):
    """Worth retrying: the same operation might succeed a few minutes
    later with no other change (lock contention, a dropped connection,
    a momentarily-unavailable resource)."""


class FatalError(Exception):
    """Not worth retrying: the operation will keep failing identically
    until a human (or a different upstream job) fixes something. Retrying
    only delays the alert and burns the retry budget for no benefit."""


class ValidationFailure(FatalError):
    """A specific FatalError raised when the post-build data-quality
    policy is violated. Kept as its own type so the alert message can be
    specific about *which* check failed, not just 'pipeline failed'."""


# --------------------------------------------------------------------------
# Logging setup
# --------------------------------------------------------------------------
class _DefaultRunIdFilter(logging.Filter):
    """Log records emitted without a run_id in `extra` (e.g. from
    notifier.py, which doesn't have run-scoped context) would otherwise
    crash the formatter, since it always expects %(run_id)s. This filter
    fills in a placeholder instead."""

    def filter(self, record):
        if not hasattr(record, "run_id"):
            record.run_id = "-"
        return True


def setup_logging(run_id: str) -> logging.LoggerAdapter:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("pipeline")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.addFilter(_DefaultRunIdFilter())

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | run=%(run_id)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "pipeline.log", maxBytes=5_000_000, backupCount=5
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logging.LoggerAdapter(logger, {"run_id": run_id})


# --------------------------------------------------------------------------
# Retry wrapper
# --------------------------------------------------------------------------
def run_with_retries(func, log, max_retries: int, delay_seconds: float, backoff: float = 1.0):
    """
    Calls func() and returns its result. On TransientError, retries up to
    max_retries times, sleeping delay_seconds * (backoff ** attempt)
    between attempts (backoff=1.0 is fixed-interval; >1.0 is exponential
    backoff). FatalError is never retried -- it propagates immediately so
    the caller can alert without wasting the retry budget.
    """
    attempt = 0
    while True:
        try:
            return func()
        except FatalError:
            raise
        except TransientError as e:
            attempt += 1
            if attempt > max_retries:
                log.error(f"Exhausted {max_retries} retries; giving up. Last error: {e}")
                raise
            wait = delay_seconds * (backoff ** (attempt - 1))
            log.warning(f"Transient failure (attempt {attempt}/{max_retries}): {e} -- retrying in {wait:.0f}s")
            time.sleep(wait)


# --------------------------------------------------------------------------
# Validation policy (built on Assignment 2's data-quality check SQL)
# --------------------------------------------------------------------------
# Each entry: (check_name, rule). rule is a function(value) -> bool, True = pass.
VALIDATION_POLICY = {
    "raw_row_count":                  lambda v: v > 0,
    "staging_duplicate_event_ids":    lambda v: v == 0,
    "users_missing_install_event":    lambda v: v == 0,
    "orphan_fact_users":              lambda v: v == 0,
    "completed_without_started":      lambda v: v == 0,
    "activated_without_completed":    lambda v: v == 0,
    "purchased_without_activated":    lambda v: v == 0,
    "invalid_test_group_values":      lambda v: v == 0,
    "mart_kpi_group_count":           lambda v: v == 3,
    "negative_time_to_first_lesson":  lambda v: v == 0,
    "kpi_rates_out_of_bounds":        lambda v: v == 0,
    # staging_rejects is deliberately NOT in this policy: a non-zero count
    # is expected (Assignment 2, Section 5.1) and is informational, not a
    # failure condition on its own.
}


def run_validation(con, log) -> dict:
    """Runs the Assignment 2 data-quality checks and evaluates each
    result against VALIDATION_POLICY. Returns a summary dict; raises
    ValidationFailure if any policed check fails."""
    results = build_db.run_quality_checks(con, ASSIGNMENT2 / "schema/05_data_quality_checks.sql")
    summary = {name: value for name, value in results}

    failures = []
    for check_name, rule in VALIDATION_POLICY.items():
        value = summary.get(check_name)
        if value is None:
            failures.append(f"{check_name}: check did not run")
        elif not rule(value):
            failures.append(f"{check_name}: value {value} violates policy")

    log.info(f"Validation: {len(VALIDATION_POLICY) - len(failures)}/{len(VALIDATION_POLICY)} policed checks passed")
    if failures:
        raise ValidationFailure("; ".join(failures))
    return summary


# --------------------------------------------------------------------------
# The pipeline itself (Assignment 2 stages, wrapped with error classification)
# --------------------------------------------------------------------------
def build_pipeline(events_csv: Path, stepmap_json: Path, db_path: Path, log, simulate: str, attempt_counter: dict) -> dict:
    """Runs one full attempt of ingest -> staging -> warehouse -> mart ->
    validate. Raises TransientError / FatalError on failure; returns the
    validation summary dict on success."""

    # --- failure simulation hooks (see 00_documentation.md Section 4) ---
    attempt_counter["n"] = attempt_counter.get("n", 0) + 1
    n = attempt_counter["n"]
    if simulate == "transient-then-ok" and n < 3:
        raise TransientError(f"simulated transient failure (attempt {n})")
    if simulate == "always-transient":
        raise TransientError(f"simulated persistent transient failure (attempt {n})")
    if simulate == "fatal-missing-file":
        events_csv = events_csv.parent / "does_not_exist.csv"
    if simulate == "bad-data":
        events_csv = _make_corrupted_copy(events_csv)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    try:
        con = sqlite3.connect(db_path, timeout=5)
    except sqlite3.OperationalError as e:
        raise TransientError(f"could not open database: {e}") from e

    try:
        log.info("[1/5] Building raw layer schema...")
        build_db.run_sql_file(con, ASSIGNMENT2 / "schema/01_raw.sql")

        log.info("[2/5] Ingesting events CSV into raw_events...")
        try:
            n_rows = build_db.load_raw_events(con, events_csv, events_csv.name)
        except FileNotFoundError as e:
            raise FatalError(
                f"source file not found: {e}. This will not resolve on retry -- "
                f"check the upstream job that produces {events_csv.name}, or the "
                f"--events-csv path, rather than relying on automatic retry."
            ) from e
        except sqlite3.OperationalError as e:
            raise TransientError(f"database busy during ingestion: {e}") from e
        log.info(f"      -> loaded {n_rows} raw rows")

        n_dirty = build_db.inject_dirty_rows(con)
        log.info(f"      -> injected {n_dirty} deliberately malformed rows (exercises staging validation)")

        log.info("[3/5] Building staging layer...")
        build_db.run_sql_file(con, ASSIGNMENT2 / "schema/02_staging.sql")

        log.info("[4/5] Building warehouse layer...")
        try:
            n_steps = build_db.load_dim_step(con, stepmap_json)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise FatalError(f"stepmap.json missing or malformed: {e}. Config error -- will not resolve on retry.") from e
        log.info(f"      -> loaded {n_steps} dim_step rows")
        build_db.run_sql_file(con, ASSIGNMENT2 / "schema/03_warehouse.sql")

        log.info("[5/5] Building data mart layer...")
        build_db.run_sql_file(con, ASSIGNMENT2 / "schema/04_datamart.sql")

        log.info("Running post-build validation...")
        summary = run_validation(con, log)

        con.commit()
        return summary

    except sqlite3.OperationalError as e:
        # anything else from SQLite mid-transaction (lock, disk I/O) is
        # treated as transient; the pipeline is idempotent (full rebuild
        # each run -- Assignment 2, Section 4), so a clean retry is safe.
        raise TransientError(str(e)) from e
    finally:
        con.close()


def _make_corrupted_copy(events_csv: Path) -> Path:
    """Simulate a data-quality problem for the --simulate bad-data demo:
    copies the real CSV but rewrites every test_group to an invalid value,
    so the staging layer's own validation rejects every row and the
    downstream validation policy (mart_kpi_group_count == 3) fails."""
    import csv
    import tempfile

    tmp = Path(tempfile.gettempdir()) / "events_corrupted.csv"
    with open(events_csv, newline="") as src, open(tmp, "w", newline="") as dst:
        reader = csv.DictReader(src)
        writer = csv.DictWriter(dst, fieldnames=reader.fieldnames)
        writer.writeheader()
        for i, row in enumerate(reader):
            row["test_group"] = "INVALID"
            writer.writerow(row)
            if i > 500:  # a few hundred corrupted rows is enough to trip the policy
                break
    return tmp


# --------------------------------------------------------------------------
# Monitoring: append every run's outcome to a JSON-lines history file
# --------------------------------------------------------------------------
def record_run(run_id, started_at, finished_at, status, retries_used, validation_summary, error=None):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "status": status,
        "retries_used": retries_used,
        "validation_summary": validation_summary,
        "error": error,
    }
    with open(RUN_HISTORY_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")
    return record


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events-csv", default=str((HERE / ".." / "assignment1/generated_data/events.csv").resolve()))
    parser.add_argument("--stepmap-json", default=str((HERE / ".." / "assignment1/stepmap.json").resolve()))
    parser.add_argument("--db", default=str((ASSIGNMENT2 / "db/ab_test.db")))
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--retry-delay-seconds", type=float, default=300,
                         help="Base delay between retries (default 300s = 5min, per the assignment brief). "
                              "Use a small value for local demos, e.g. --retry-delay-seconds 2")
    parser.add_argument("--backoff", type=float, default=1.0,
                         help="Multiplier applied to retry-delay each attempt. 1.0 = fixed interval, "
                              "2.0 = exponential backoff (5min, 10min, 20min, ...)")
    parser.add_argument("--simulate", choices=["none", "transient-then-ok", "always-transient",
                                                 "fatal-missing-file", "bad-data"], default="none",
                         help="Inject a failure mode to demonstrate retry/alert behavior without waiting for a real one")
    args = parser.parse_args()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid.uuid4().hex[:8]
    log = setup_logging(run_id)
    notifier = LogNotifier()

    started_at = datetime.now(timezone.utc)
    log.info(f"=== Pipeline run {run_id} starting (simulate={args.simulate}) ===")

    attempt_counter = {}
    try:
        summary = run_with_retries(
            func=lambda: build_pipeline(
                Path(args.events_csv), Path(args.stepmap_json), Path(args.db),
                log, args.simulate, attempt_counter,
            ),
            log=log,
            max_retries=args.max_retries,
            delay_seconds=args.retry_delay_seconds,
            backoff=args.backoff,
        )
        finished_at = datetime.now(timezone.utc)
        retries_used = attempt_counter.get("n", 1) - 1
        record_run(run_id, started_at, finished_at, "success", retries_used, summary)
        log.info(f"=== Pipeline run {run_id} SUCCEEDED after {retries_used} retries "
                  f"({(finished_at - started_at).total_seconds():.1f}s) ===")
        return 0

    except ValidationFailure as e:
        finished_at = datetime.now(timezone.utc)
        retries_used = attempt_counter.get("n", 1) - 1
        record_run(run_id, started_at, finished_at, "failed_validation", retries_used, None, str(e))
        notifier.notify(
            subject=f"Pipeline run {run_id} FAILED data validation",
            message=f"Post-build validation policy violated (not retried -- same input would fail again):\n{e}",
        )
        log.critical(f"=== Pipeline run {run_id} FAILED (validation) ===")
        return 1

    except FatalError as e:
        finished_at = datetime.now(timezone.utc)
        retries_used = attempt_counter.get("n", 1) - 1
        record_run(run_id, started_at, finished_at, "failed_fatal", retries_used, None, str(e))
        notifier.notify(
            subject=f"Pipeline run {run_id} FAILED (fatal, not retried)",
            message=str(e),
        )
        log.critical(f"=== Pipeline run {run_id} FAILED (fatal) ===")
        return 1

    except TransientError as e:
        finished_at = datetime.now(timezone.utc)
        retries_used = attempt_counter.get("n", 1) - 1
        record_run(run_id, started_at, finished_at, "failed_retries_exhausted", retries_used, None, str(e))
        notifier.notify(
            subject=f"Pipeline run {run_id} FAILED after {retries_used} retries",
            message=f"Last error: {e}\n\nOwner/stakeholders should investigate the upstream "
                     f"cause (connection/server issue) before the next scheduled run.",
        )
        log.critical(f"=== Pipeline run {run_id} FAILED (retries exhausted) ===")
        return 1

    except Exception as e:
        # Anything not already classified is treated as fatal-and-alert
        # rather than silently retried, since an unclassified exception
        # might indicate a bug -- retrying blindly could mask it.
        finished_at = datetime.now(timezone.utc)
        record_run(run_id, started_at, finished_at, "failed_unclassified", 0, None, str(e))
        notifier.notify(
            subject=f"Pipeline run {run_id} FAILED (unclassified error)",
            message=f"{type(e).__name__}: {e}\n\nThis error type isn't in the retry/fatal taxonomy yet -- "
                     f"treated as fatal out of caution. Consider classifying it in pipeline_runner.py.",
        )
        log.exception(f"=== Pipeline run {run_id} FAILED (unclassified) ===")
        return 1


if __name__ == "__main__":
    sys.exit(main())
