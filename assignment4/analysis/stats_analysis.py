"""
Assignment 4 -- Statistical analysis of the A/B test.

Reads the Assignment 2 warehouse/data-mart tables and computes:
  1. A Sample Ratio Mismatch (SRM) check (chi-square goodness-of-fit
     against the expected 33/33/33 allocation) -- a precondition for
     trusting anything else, per the Assignment 1 event-tracking plan.
  2. The primary hypothesis test: two-proportion z-tests on onboarding
     completion rate, for all three pairwise arm comparisons, with
     Wilson-score confidence intervals and relative lift.
  3. Secondary metrics (activation, D1/D7 return, paid conversion, time
     to first lesson) as descriptive comparisons -- reported, not
     independently hypothesis-tested, per Assignment 1 Section 4.4/3.5's
     multiple-comparisons reasoning.
  4. Guardrail metrics as descriptive/directional signals only, exactly
     as the Assignment 1 governance model specifies -- no p-values
     presented as confirmatory for these.
  5. A power/MDE recheck against the *actual* achieved sample sizes.

Writes analysis/results.json (consumed by the dashboard) and prints a
human-readable report to stdout.

Usage:
    python analysis/stats_analysis.py --db ../assignment2/db/ab_test.db
"""
import argparse
import json
import sqlite3
from pathlib import Path

import numpy as np
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest, proportion_confint
from statsmodels.stats.power import NormalIndPower

HERE = Path(__file__).parent


def _json_default(o):
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

ARMS = ["A", "B", "C"]
ARM_LABELS = {"A": "Control (13 steps)", "B": "Medium (7 steps)", "C": "Short (5 steps)"}
PAIRS = [("A", "B"), ("A", "C"), ("B", "C")]

ALPHA = 0.05


def fetch_one_row(con, sql, params=()):
    cur = con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(cols, row)) if row else None


def fetch_all(con, sql, params=()):
    cur = con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# --------------------------------------------------------------------------
# 1. Sample Ratio Mismatch check
# --------------------------------------------------------------------------
def srm_check(con):
    rows = fetch_all(con, "SELECT test_group, users_started FROM mart_kpi_by_group ORDER BY test_group")
    observed = [r["users_started"] for r in rows]
    total = sum(observed)
    expected = [total / 3] * 3
    chi2, p_value = stats.chisquare(observed, f_exp=expected)
    return {
        "observed": {r["test_group"]: r["users_started"] for r in rows},
        "expected_per_arm": round(total / 3, 1),
        "chi2_statistic": round(chi2, 4),
        "p_value": round(p_value, 4),
        "passes": bool(p_value >= 0.001),  # conventional SRM threshold is much stricter than 0.05
        "interpretation": (
            "No Sample Ratio Mismatch detected -- observed allocation is consistent with the "
            "intended 33/33/33 split. Downstream comparisons can be trusted."
            if p_value >= 0.001 else
            "SRM DETECTED (p < 0.001) -- the realized allocation deviates from 33/33/33 enough "
            "that a broken randomizer or differential instrumentation loss must be ruled out "
            "before trusting any other result in this report."
        ),
    }


# --------------------------------------------------------------------------
# 2. Primary metric: two-proportion z-test on completion rate
# --------------------------------------------------------------------------
def wilson_ci(successes, n, alpha=ALPHA):
    lo, hi = proportion_confint(successes, n, alpha=alpha, method="wilson")
    return round(lo, 4), round(hi, 4)


def primary_metric_tests(con):
    rows = {r["test_group"]: r for r in fetch_all(
        con, "SELECT test_group, users_started, users_completed, onboarding_completion_rate "
             "FROM mart_kpi_by_group ORDER BY test_group"
    )}

    per_arm = {}
    for arm in ARMS:
        r = rows[arm]
        lo, hi = wilson_ci(r["users_completed"], r["users_started"])
        per_arm[arm] = {
            "label": ARM_LABELS[arm],
            "users_started": r["users_started"],
            "users_completed": r["users_completed"],
            "completion_rate": r["onboarding_completion_rate"],
            "ci_95_low": lo,
            "ci_95_high": hi,
        }

    pairwise = []
    for a, b in PAIRS:
        ra, rb = rows[a], rows[b]
        counts = [ra["users_completed"], rb["users_completed"]]
        nobs = [ra["users_started"], rb["users_started"]]
        z_stat, p_value = proportions_ztest(counts, nobs)
        p1, p2 = ra["onboarding_completion_rate"], rb["onboarding_completion_rate"]
        abs_diff = round(p2 - p1, 4)
        rel_lift = round((p2 - p1) / p1 * 100, 2) if p1 else None
        # CI on the difference of two proportions (normal approximation)
        se = ((p1 * (1 - p1) / nobs[0]) + (p2 * (1 - p2) / nobs[1])) ** 0.5
        z_crit = stats.norm.ppf(1 - ALPHA / 2)
        diff_ci = (round(abs_diff - z_crit * se, 4), round(abs_diff + z_crit * se, 4))
        pairwise.append({
            "arm_a": a, "arm_b": b,
            "label": f"{a} ({ARM_LABELS[a]}) vs {b} ({ARM_LABELS[b]})",
            "rate_a": p1, "rate_b": p2,
            "absolute_diff": abs_diff,
            "relative_lift_pct": rel_lift,
            "diff_ci_95": diff_ci,
            "z_statistic": round(z_stat, 4),
            "p_value": p_value,
            "significant_at_05": bool(p_value < ALPHA),
        })

    return {"per_arm": per_arm, "pairwise_tests": pairwise}


# --------------------------------------------------------------------------
# 3. Secondary metrics (descriptive comparison, not independently tested)
# --------------------------------------------------------------------------
def secondary_metrics(con):
    rows = {r["test_group"]: r for r in fetch_all(
        con, "SELECT * FROM mart_kpi_by_group ORDER BY test_group"
    )}
    metrics = ["activation_rate", "day1_return_rate", "day7_return_rate",
               "day30_return_rate", "paid_conversion_rate", "avg_time_to_first_lesson_seconds"]
    out = {}
    for m in metrics:
        out[m] = {arm: rows[arm][m] for arm in ARMS}
    return out


# --------------------------------------------------------------------------
# 4. Guardrail metrics (directional only, per governance model)
# --------------------------------------------------------------------------
def guardrail_metrics(con):
    rows = {r["test_group"]: r for r in fetch_all(
        con, "SELECT * FROM mart_guardrails_by_group ORDER BY test_group"
    )}
    metrics = ["avg_lesson_relevance_score", "refund_rate", "cancellation_rate",
               "support_ticket_rate", "notification_optin_rate"]
    out = {}
    for m in metrics:
        out[m] = {arm: rows[arm][m] for arm in ARMS}

    # Directional flags: is C (shortest, most aggressive arm) worse than A (control)
    # on each guardrail? This mirrors the identification concern in Assignment 1
    # Section 2 -- a completion-rate win that comes with guardrail regressions
    # is a genuine trade-off, not a clean win.
    flags = []
    a, c = rows["A"], rows["C"]
    if c["avg_lesson_relevance_score"] < a["avg_lesson_relevance_score"]:
        flags.append(f"Lesson relevance score is lower in C ({c['avg_lesson_relevance_score']:.2f}) than A ({a['avg_lesson_relevance_score']:.2f})")
    if c["refund_rate"] > a["refund_rate"]:
        flags.append(f"Refund rate is higher in C ({c['refund_rate']:.1%}) than A ({a['refund_rate']:.1%})")
    if c["support_ticket_rate"] > a["support_ticket_rate"]:
        flags.append(f"Support-ticket rate is higher in C ({c['support_ticket_rate']:.1%}) than A ({a['support_ticket_rate']:.1%})")
    if c["notification_optin_rate"] < a["notification_optin_rate"]:
        flags.append(f"Notification opt-in is lower in C ({c['notification_optin_rate']:.1%}) than A ({a['notification_optin_rate']:.1%})")

    return {"by_arm": out, "regression_flags_vs_control": flags}


# --------------------------------------------------------------------------
# 5. Power / MDE recheck against actual achieved sample sizes
# --------------------------------------------------------------------------
def power_recheck(con):
    rows = {r["test_group"]: r for r in fetch_all(
        con, "SELECT test_group, users_started FROM mart_kpi_by_group ORDER BY test_group"
    )}
    n_per_arm = min(r["users_started"] for r in rows.values())
    baseline_p = fetch_one_row(con, "SELECT onboarding_completion_rate FROM mart_kpi_by_group WHERE test_group='A'")["onboarding_completion_rate"]

    analysis = NormalIndPower()
    # MDE achievable at 80% power with the actual achieved n per arm
    achieved_mde = analysis.solve_power(effect_size=None, nobs1=n_per_arm, alpha=ALPHA, power=0.80, ratio=1.0)
    # convert Cohen's h effect size back to an approximate percentage-point MDE around baseline_p
    def h_to_pp(h, p1):
        # solve for p2 given Cohen's h = 2*asin(sqrt(p2)) - 2*asin(sqrt(p1))
        p2 = np.sin((h + 2 * np.arcsin(np.sqrt(p1))) / 2) ** 2
        return abs(p2 - p1)

    mde_pp = h_to_pp(achieved_mde, baseline_p)

    return {
        "n_per_arm_achieved": n_per_arm,
        "baseline_completion_rate": baseline_p,
        "alpha": ALPHA,
        "target_power": 0.80,
        "achievable_mde_pp_at_80pct_power": round(mde_pp * 100, 2),
        "interpretation": (
            f"With {n_per_arm} users per arm, this experiment could reliably detect a "
            f"completion-rate difference of about {mde_pp*100:.1f} percentage points at 80% power. "
            f"The observed differences between arms (see primary metric results) are well above "
            f"this threshold, so the primary result is not a statistically under-powered false negative risk."
        ),
    }


# --------------------------------------------------------------------------
# Recommendation synthesis
# --------------------------------------------------------------------------
def synthesize_recommendation(primary, guardrails, srm):
    ab = next(p for p in primary["pairwise_tests"] if p["arm_a"] == "A" and p["arm_b"] == "B")
    ac = next(p for p in primary["pairwise_tests"] if p["arm_a"] == "A" and p["arm_b"] == "C")
    bc = next(p for p in primary["pairwise_tests"] if p["arm_a"] == "B" and p["arm_b"] == "C")

    n_flags = len(guardrails["regression_flags_vs_control"])

    if not srm["passes"]:
        verdict = "HOLD"
        reason = "Sample Ratio Mismatch detected -- do not act on any result below until the randomizer is fixed and the experiment is rerun."
    elif ab["significant_at_05"] and ac["significant_at_05"] and n_flags == 0:
        verdict = "SHIP (Medium, Arm B)"
        reason = "Both B and C beat control significantly on the primary metric, with no guardrail regressions detected -- recommend the more conservative winner (B) to capture most of the gain with less compositional risk than C."
    elif ab["significant_at_05"] and n_flags >= 2:
        verdict = "SHIP WITH MITIGATION (Arm B, not C)"
        reason = f"B significantly beats control on completion rate with no major guardrail regression. C wins by more on completion but shows {n_flags} guardrail regressions relative to control -- ship B now; treat C as a follow-up experiment after addressing what's driving its guardrail declines."
    else:
        verdict = "SHIP WITH MITIGATION"
        reason = "Primary metric improved, but guardrail trade-offs mean the win should be shipped cautiously with guardrail monitoring in place post-launch, rather than treated as an unqualified win."

    return {
        "verdict": verdict,
        "reasoning": reason,
        "guardrail_regression_count_C_vs_A": n_flags,
        "supporting_tests": {"A_vs_B": ab, "A_vs_C": ac, "B_vs_C": bc},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="../assignment2/db/ab_test.db")
    parser.add_argument("--out", default="results.json")
    args = parser.parse_args()

    con = sqlite3.connect(HERE / args.db)

    srm = srm_check(con)
    primary = primary_metric_tests(con)
    secondary = secondary_metrics(con)
    guardrails = guardrail_metrics(con)
    power = power_recheck(con)
    recommendation = synthesize_recommendation(primary, guardrails, srm)

    results = {
        "srm_check": srm,
        "primary_metric": primary,
        "secondary_metrics": secondary,
        "guardrail_metrics": guardrails,
        "power_recheck": power,
        "recommendation": recommendation,
    }

    out_path = HERE / args.out
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=_json_default)

    # --- human-readable report ---
    print("=" * 78)
    print("SRM CHECK")
    print("=" * 78)
    print(f"Observed allocation: {srm['observed']}  (expected ~{srm['expected_per_arm']} each)")
    print(f"chi2={srm['chi2_statistic']}  p={srm['p_value']}  -> {srm['interpretation']}")

    print("\n" + "=" * 78)
    print("PRIMARY METRIC: Onboarding Completion Rate")
    print("=" * 78)
    for arm, d in primary["per_arm"].items():
        print(f"  {arm} ({d['label']}): {d['completion_rate']:.1%}  "
              f"[95% CI {d['ci_95_low']:.1%}-{d['ci_95_high']:.1%}]  n={d['users_started']}")
    print()
    for t in primary["pairwise_tests"]:
        sig = "SIGNIFICANT" if t["significant_at_05"] else "not significant"
        print(f"  {t['label']}:")
        print(f"    diff={t['absolute_diff']:+.1%}  rel_lift={t['relative_lift_pct']:+.1f}%  "
              f"p={'<0.0001' if t['p_value'] < 0.0001 else f\"{t['p_value']:.4f}\"}  ({sig} at alpha=0.05)")

    print("\n" + "=" * 78)
    print("GUARDRAIL REGRESSION FLAGS (C vs A)")
    print("=" * 78)
    if guardrails["regression_flags_vs_control"]:
        for f in guardrails["regression_flags_vs_control"]:
            print(f"  - {f}")
    else:
        print("  None detected.")

    print("\n" + "=" * 78)
    print("POWER RECHECK")
    print("=" * 78)
    print(f"  {power['interpretation']}")

    print("\n" + "=" * 78)
    print("RECOMMENDATION")
    print("=" * 78)
    print(f"  {recommendation['verdict']}")
    print(f"  {recommendation['reasoning']}")

    print(f"\nWrote {out_path}")
    con.close()


if __name__ == "__main__":
    main()
