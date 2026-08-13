"""
Synthetic event data generator for the Onboarding Flow Optimization A/B test.

Simulates realistic, event-level clickstream data for three onboarding
variants (A = 13-step control, B = 7-step medium, C = 5-step short), matching
the event schema in event_schema.json and the step maps in stepmap.json.

Effects deliberately baked into the simulation (so Assignment 4's statistical
analysis has something real to find, not just "shorter always wins"):
  - Per-step abandonment compounds with a fatigue multiplier that grows with
    step position -> completion rate A < B < C, roughly 60% / 73% / 80%.
  - C (shortest) trades completion for slightly worse personalization/
    guardrail outcomes: lower lesson relevance score, lower Day-30 return,
    higher refund rate, higher onboarding-related support tickets, and a
    lower notification opt-in rate (since that step is dropped for C and
    only asked for later, after first lesson).
  - Paid conversion rate off of activated users is held roughly constant
    across groups (~6%), matching the business doc's finding that the
    checkout/conversion mechanics themselves aren't the problem.

Usage:
    python data_generator.py --n-users 30000 --seed 42 --out generated_data/events.csv
"""
import argparse
import csv
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent

with open(HERE / "stepmap.json") as f:
    STEPMAP = json.load(f)

STEP_LOOKUP = {s["step_name"]: s for s in STEPMAP["all_steps_master_list"]}
VARIANTS = STEPMAP["variants"]

INSTALL_WINDOW_START = datetime(2026, 6, 15, tzinfo=timezone.utc)
INSTALL_WINDOW_DAYS = 30

# Fatigue multiplier per variant: how much each successive step's abandon
# probability grows relative to the base rate (simulates onboarding fatigue
# for longer flows). Calibrated together with BASE_ABANDON_MULT below so
# simulated completion rates land close to A ~60%, B ~73%, C ~80% (matching
# the business document's numbers).
FATIGUE = {"A": 0.015, "B": 0.006, "C": 0.003}
BASE_ABANDON_MULT = 0.88

# Approx guardrail modifiers by variant, applied relative to variant A baseline
GUARDRAIL = {
    "A": {"relevance_mu": 4.1, "day30_return": 0.34, "refund_rate": 0.02, "support_rate": 0.015, "notif_optin": 0.55},
    "B": {"relevance_mu": 3.9, "day30_return": 0.33, "refund_rate": 0.025, "support_rate": 0.018, "notif_optin": 0.50},
    "C": {"relevance_mu": 3.5, "day30_return": 0.27, "refund_rate": 0.035, "support_rate": 0.028, "notif_optin": 0.30},
}

PAID_CONVERSION_RATE = 0.06  # of activated users, ~flat across groups per business doc


def new_id():
    return str(uuid.uuid4())


def choose_group_and_platform(rng, i):
    # stratified so iOS/Android are balanced within each group
    group = ["A", "B", "C"][i % 3]
    platform = "iOS" if (i // 3) % 2 == 0 else "Android"
    return group, platform


class EventWriter:
    def __init__(self, path):
        self.f = open(path, "w", newline="")
        self.writer = csv.writer(self.f)
        self.writer.writerow(
            ["event_id", "user_id", "event_name", "event_timestamp",
             "test_group", "platform", "session_id", "properties"]
        )

    def emit(self, user_id, event_name, ts, group, platform, session_id, **props):
        self.writer.writerow([
            new_id(), user_id, event_name, ts.isoformat(),
            group, platform, session_id, json.dumps(props, default=str),
        ])

    def close(self):
        self.f.close()


def simulate_user(rng, user_idx, writer):
    user_id = f"u_{user_idx:07d}"
    group, platform = choose_group_and_platform(rng, user_idx)
    install_offset = rng.uniform(0, INSTALL_WINDOW_DAYS)
    install_ts = INSTALL_WINDOW_START + timedelta(days=install_offset)
    session_id = new_id()

    writer.emit(user_id, "app_installed", install_ts, group, platform, session_id,
                device_platform=platform)

    step_names = VARIANTS[group]["step_names"]
    total_steps = len(step_names)
    fatigue = FATIGUE[group]
    guard = GUARDRAIL[group]

    ts = install_ts + timedelta(seconds=rng.uniform(5, 60))
    writer.emit(user_id, "onboarding_started", ts, group, platform, session_id,
                total_steps_in_flow=total_steps)

    completed_all = True
    steps_completed = 0
    account_created = False

    for pos, step_name in enumerate(step_names, start=1):
        meta = STEP_LOOKUP[step_name]
        writer.emit(user_id, "onboarding_step_viewed", ts, group, platform, session_id,
                    step_number=pos, step_name=step_name, step_bucket=meta["bucket"])

        abandon_p = min(0.9, meta["base_abandon_rate"] * BASE_ABANDON_MULT * (1 + fatigue * (pos - 1)))
        time_on_step = max(2, rng.gauss(18, 6))
        ts = ts + timedelta(seconds=time_on_step)

        if rng.random() < abandon_p:
            writer.emit(user_id, "onboarding_step_abandoned", ts, group, platform, session_id,
                        step_number=pos, step_name=step_name,
                        exit_reason=rng.choice(["closed_app", "backgrounded", "timeout", "unknown"]))
            completed_all = False
            break

        writer.emit(user_id, "onboarding_step_completed", ts, group, platform, session_id,
                    step_number=pos, step_name=step_name, time_on_step_seconds=round(time_on_step, 1))
        steps_completed += 1

        if step_name == "account_creation_password" and not account_created:
            writer.emit(user_id, "account_created", ts, group, platform, session_id,
                        signup_method=rng.choice(["email", "google", "apple"]))
            account_created = True

        if step_name == "notification_permission":
            writer.emit(user_id, "notification_permission_shown", ts, group, platform, session_id)
            if rng.random() < guard["notif_optin"]:
                writer.emit(user_id, "notification_permission_accepted", ts, group, platform, session_id)
            else:
                writer.emit(user_id, "notification_permission_denied", ts, group, platform, session_id)

    if not completed_all:
        return  # funnel ends here for this user

    writer.emit(user_id, "onboarding_completed", ts, group, platform, session_id,
                total_time_seconds=round((ts - install_ts).total_seconds(), 1),
                steps_completed=steps_completed)

    # Deferred notification prompt for variants that don't have the step in-flow (C)
    if "notification_permission" not in step_names:
        ts_notif = ts + timedelta(minutes=rng.uniform(2, 30))
        writer.emit(user_id, "notification_permission_shown", ts_notif, group, platform, session_id)
        if rng.random() < guard["notif_optin"]:
            writer.emit(user_id, "notification_permission_accepted", ts_notif, group, platform, session_id)
        else:
            writer.emit(user_id, "notification_permission_denied", ts_notif, group, platform, session_id)

    # --- Activation ---
    if rng.random() < 0.85:
        lesson_id = f"lesson_{rng.randint(1, 20):03d}"
        ts_ls = ts + timedelta(minutes=rng.uniform(1, 45))
        writer.emit(user_id, "first_lesson_started", ts_ls, group, platform, session_id,
                    lesson_id=lesson_id)

        if rng.random() < 0.78:
            ts_lc = ts_ls + timedelta(minutes=rng.uniform(3, 20))
            score = max(0, min(100, round(rng.gauss(72, 15))))
            writer.emit(user_id, "first_lesson_completed", ts_lc, group, platform, session_id,
                        lesson_id=lesson_id, score=score)
            activated = True
        else:
            activated = False
    else:
        activated = False

    # --- Lesson feedback (guardrail: personalization quality) ---
    if activated and rng.random() < 0.4:
        rel_score = max(1, min(5, round(rng.gauss(guard["relevance_mu"], 0.9))))
        writer.emit(user_id, "lesson_feedback_submitted", ts, group, platform, session_id,
                    relevance_score=rel_score)

    # --- Retention ---
    for day, event_name in [(1, "app_opened_day1"), (7, "app_opened_day7"), (30, "app_opened_day30")]:
        base_p = {1: 0.55, 7: 0.40, 30: guard["day30_return"]}[day]
        p = base_p * (1.25 if activated else 0.6)
        if rng.random() < min(0.95, p):
            ts_ret = install_ts + timedelta(days=day, hours=rng.uniform(-3, 3))
            session_ret = new_id()
            writer.emit(user_id, event_name, ts_ret, group, platform, session_ret,
                        days_since_install=day)

    # --- Monetization ---
    if activated and rng.random() < 0.30:
        ts_trial = ts + timedelta(days=rng.uniform(0, 2))
        writer.emit(user_id, "trial_started", ts_trial, group, platform, session_id,
                    trial_length_days=7)

        if rng.random() < (PAID_CONVERSION_RATE / 0.30):
            ts_purchase = ts_trial + timedelta(days=7 + rng.uniform(0, 2))
            plan = rng.choice(["monthly", "annual"])
            price = 12.99 if plan == "monthly" else 89.99
            writer.emit(user_id, "subscription_purchased", ts_purchase, group, platform, session_id,
                        plan=plan, price_usd=price)

            if rng.random() < guard["refund_rate"]:
                ts_refund = ts_purchase + timedelta(days=rng.uniform(0.5, 10))
                writer.emit(user_id, "refund_requested", ts_refund, group, platform, session_id,
                            days_since_purchase=round((ts_refund - ts_purchase).days, 1),
                            reason=rng.choice(["not_as_expected", "too_expensive", "found_free_alternative", "other"]))
            elif rng.random() < 0.08:
                ts_cancel = ts_purchase + timedelta(days=rng.uniform(10, 45))
                writer.emit(user_id, "subscription_cancelled", ts_cancel, group, platform, session_id,
                            days_since_purchase=round((ts_cancel - ts_purchase).days, 1))

    # --- Support tickets (guardrail) ---
    if rng.random() < guard["support_rate"]:
        ts_ticket = ts + timedelta(hours=rng.uniform(1, 72))
        writer.emit(user_id, "support_ticket_created", ts_ticket, group, platform, session_id,
                    is_onboarding_related=True,
                    category=rng.choice(["billing_confusion", "permission_confusion", "cant_find_feature", "other"]))

    # --- Background noise: crashes/errors, independent of group ---
    if rng.random() < 0.015:
        writer.emit(user_id, rng.choice(["app_crash", "app_error"]), ts + timedelta(minutes=rng.uniform(1, 100)),
                    group, platform, session_id,
                    error_code=f"E{rng.randint(100, 999)}", screen=rng.choice(["onboarding", "lesson", "home", "checkout"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-users", type=int, default=30000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="generated_data/events.csv")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    out_path = HERE / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    writer = EventWriter(out_path)
    for i in range(args.n_users):
        simulate_user(rng, i, writer)
    writer.close()

    print(f"Wrote events for {args.n_users} users to {out_path}")


if __name__ == "__main__":
    main()
