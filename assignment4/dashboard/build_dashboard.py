"""
Builds the Assignment 4 analytics dashboard entirely in Python
(matplotlib + seaborn) -- no HTML/JS. Produces:
  - dashboard.png: one composite figure, laid out like a real analytics
    dashboard (KPI summary cards, completion-rate chart with 95% CIs,
    guardrail comparison, step drop-off funnel, daily trend, and a
    recommendation panel), suitable for embedding directly in a report.
  - Individual chart PNGs (completion_rate.png, guardrails.png,
    step_dropoff.png, daily_trend.png) at higher resolution, for anyone
    who wants a single chart rather than the composite.

Reads dashboard_data.json (built by data_export.py), which itself merges
the Assignment 2 data-mart tables with the Assignment 4 statistical
results (stats_analysis.py) -- no numbers are computed in this file;
it only visualizes what those two scripts already computed.

Usage:
    python dashboard/build_dashboard.py
"""
import json
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import numpy as np

HERE = Path(__file__).parent
OUT_DIR = HERE
CHART_DIR = HERE / "charts"
CHART_DIR.mkdir(exist_ok=True)

NAVY = "#10243e"
MIDBLUE = "#3a5a80"
LIGHTBLUE = "#c9d9ea"
PANEL = "#f4f7fa"
GREEN = "#2f6b3f"
AMBER = "#7a5a1e"
RED = "#7a3b3b"
GREY = "#6b7685"

ARM_COLORS = {"A": "#7a3b3b", "B": "#3a5a80", "C": "#10243e"}
ARM_LABELS = {"A": "A \u2014 Control\n(13 steps)", "B": "B \u2014 Medium\n(7 steps)", "C": "C \u2014 Short\n(5 steps)"}
ARM_LABELS_SHORT = {"A": "A (Control)", "B": "B (Medium)", "C": "C (Short)"}

plt.rcParams.update({
    "font.family": "serif",
    "axes.edgecolor": "#c9d2db",
    "axes.labelcolor": "#333333",
    "text.color": "#1a1a1a",
    "xtick.color": "#444444",
    "ytick.color": "#444444",
    "axes.titleweight": "bold",
    "axes.titlecolor": NAVY,
})


def load_data():
    with open(HERE / "dashboard_data.json") as f:
        return json.load(f)


def kpi_dict(data, table):
    return {r["test_group"]: r for r in data[table]}


# --------------------------------------------------------------------------
# Individual chart functions -- each both draws into a given Axes (for the
# composite dashboard) AND can be saved standalone at higher DPI.
# --------------------------------------------------------------------------
def plot_completion_rate(ax, stats):
    arms = ["A", "B", "C"]
    per_arm = stats["primary_metric"]["per_arm"]
    rates = [per_arm[a]["completion_rate"] * 100 for a in arms]
    lo = [per_arm[a]["ci_95_low"] * 100 for a in arms]
    hi = [per_arm[a]["ci_95_high"] * 100 for a in arms]
    err = [[r - l for r, l in zip(rates, lo)], [h - r for r, h in zip(rates, hi)]]

    bars = ax.bar(range(3), rates, color=[ARM_COLORS[a] for a in arms], width=0.55,
                   yerr=err, capsize=5, ecolor="#333333", error_kw={"linewidth": 1.3})
    for i, r in enumerate(rates):
        ax.text(i, r + 3.2, f"{r:.1f}%", ha="center", fontsize=10.5, fontweight="bold", color=NAVY)

    # significance brackets
    def sig_bracket(x1, x2, y, label):
        ax.plot([x1, x1, x2, x2], [y, y + 1.5, y + 1.5, y], color="#333", linewidth=1)
        ax.text((x1 + x2) / 2, y + 2, label, ha="center", fontsize=9, color="#333")

    sig_bracket(0, 1, 88, "p < 0.0001")
    sig_bracket(1, 2, 94, "p < 0.0001")
    sig_bracket(0, 2, 100, "p < 0.0001")

    ax.set_xticks(range(3))
    ax.set_xticklabels([ARM_LABELS[a] for a in arms], fontsize=9.5)
    ax.set_ylabel("Onboarding Completion Rate (%)")
    ax.set_ylim(0, 112)
    ax.set_title("Primary Metric: Onboarding Completion Rate (95% CI)")
    ax.spines[["top", "right"]].set_visible(False)


def plot_guardrails(ax, data):
    arms = ["A", "B", "C"]
    g = kpi_dict(data, "guardrails_by_group")
    metrics = [
        ("avg_lesson_relevance_score", "Lesson\nRelevance\n(1-5)", 1),
        ("refund_rate", "Refund\nRate (%)", 100),
        ("support_ticket_rate", "Support\nTickets (%)", 100),
        ("notification_optin_rate", "Notification\nOpt-in (%)", 100),
    ]
    x = np.arange(len(metrics))
    width = 0.26
    for i, a in enumerate(arms):
        vals = [g[a][m[0]] * m[2] for m in metrics]
        ax.bar(x + (i - 1) * width, vals, width, color=ARM_COLORS[a], label=ARM_LABELS_SHORT[a])
    ax.set_xticks(x)
    ax.set_xticklabels([m[1] for m in metrics], fontsize=9)
    ax.set_title("Guardrail Metrics by Arm")
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)


def plot_step_dropoff(ax, data):
    arms = ["A", "B", "C"]
    rows = data["step_dropoff"]
    for a in arms:
        arm_rows = sorted([r for r in rows if r["test_group"] == a], key=lambda r: r["step_number"])
        x = [r["step_number"] for r in arm_rows]
        y = [r["step_abandon_rate"] * 100 for r in arm_rows]
        ax.plot(x, y, marker="o", markersize=4, color=ARM_COLORS[a], label=ARM_LABELS_SHORT[a], linewidth=1.8)
    ax.set_xlabel("Step Number")
    ax.set_ylabel("Abandon Rate (%)")
    ax.set_title("Step-Level Abandon Rate")
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)


def plot_daily_trend(ax, data):
    arms = ["A", "B", "C"]
    rows = data["daily_funnel"]
    for a in arms:
        arm_rows = sorted([r for r in rows if r["test_group"] == a], key=lambda r: r["install_date"])
        x = [r["install_date"][5:] for r in arm_rows]  # MM-DD
        y = [r["onboarding_completion_rate"] * 100 for r in arm_rows]
        ax.plot(x, y, color=ARM_COLORS[a], linewidth=1.3, alpha=0.85, label=ARM_LABELS_SHORT[a])
    ax.set_ylabel("Completion Rate (%)")
    ax.set_title("Daily Completion Rate Trend")
    n = len(rows) // 3
    tick_idx = list(range(0, n, max(1, n // 6)))
    ax.set_xticks(tick_idx)
    ax.set_xticklabels([sorted(set(r["install_date"][5:] for r in rows))[i] for i in tick_idx], rotation=45, fontsize=8)
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)


def draw_kpi_cards(ax, stats):
    ax.axis("off")
    arms = ["A", "B", "C"]
    per_arm = stats["primary_metric"]["per_arm"]
    srm = stats["srm_check"]
    for i, a in enumerate(arms):
        x0 = i / 3
        rect = mpatches.FancyBboxPatch((x0 + 0.01, 0.05), 0.31, 0.9, boxstyle="round,pad=0.01,rounding_size=0.02",
                                        transform=ax.transAxes, facecolor=PANEL, edgecolor=ARM_COLORS[a], linewidth=2.2)
        ax.add_patch(rect)
        ax.text(x0 + 0.165, 0.78, ARM_LABELS_SHORT[a], transform=ax.transAxes, ha="center", fontsize=10, fontweight="bold", color=NAVY)
        ax.text(x0 + 0.165, 0.48, f"{per_arm[a]['completion_rate']*100:.1f}%", transform=ax.transAxes, ha="center", fontsize=22, fontweight="bold", color=ARM_COLORS[a])
        ax.text(x0 + 0.165, 0.22, f"n={per_arm[a]['users_started']:,}  CI[{per_arm[a]['ci_95_low']*100:.1f}, {per_arm[a]['ci_95_high']*100:.1f}]%",
                transform=ax.transAxes, ha="center", fontsize=8, color="#555")
    ax.text(0.5, -0.18, f"SRM check: \u03c7\u00b2={srm['chi2_statistic']}, p={srm['p_value']} \u2014 {srm['interpretation'].split('.')[0]}.",
            transform=ax.transAxes, ha="center", fontsize=8.5, color=GREEN if srm["passes"] else RED, style="italic")


def draw_recommendation(ax, stats):
    ax.axis("off")
    rec = stats["recommendation"]
    color = GREEN if rec["verdict"].startswith("SHIP (") else AMBER if "MITIGATION" in rec["verdict"] else RED
    rect = mpatches.FancyBboxPatch((0.01, 0.05), 0.98, 0.9, boxstyle="round,pad=0.01,rounding_size=0.02",
                                    transform=ax.transAxes, facecolor="#fbf1e0" if color == AMBER else "#eaf5ee" if color == GREEN else "#f8e9e9",
                                    edgecolor=color, linewidth=2)
    ax.add_patch(rect)
    ax.text(0.04, 0.68, rec["verdict"], transform=ax.transAxes, fontsize=13, fontweight="bold", color=color)
    wrapped = textwrap.fill(rec["reasoning"], width=110)
    ax.text(0.04, 0.48, wrapped, transform=ax.transAxes, fontsize=9, color="#333", va="top")


# --------------------------------------------------------------------------
# Composite dashboard
# --------------------------------------------------------------------------
def build_composite(data):
    stats = data["stats"]
    fig = plt.figure(figsize=(14, 12.5))
    fig.patch.set_facecolor("white")
    gs = GridSpec(4, 2, figure=fig, height_ratios=[0.55, 1.3, 1.3, 0.6], hspace=0.55, wspace=0.28,
                  top=0.94, bottom=0.04, left=0.07, right=0.96)

    fig.text(0.5, 0.98, "Onboarding Flow Optimization \u2014 Experiment Evaluation Dashboard", ha="center", fontsize=17, fontweight="bold", color=NAVY)
    fig.text(0.5, 0.965, "3-arm A/B test (13 / 7 / 5 onboarding steps)  \u00b7  Assignment 4  \u00b7  Aishwarya Mishra, USN 2648610, Christ University",
             ha="center", fontsize=9.5, color=GREY, style="italic")

    ax_kpi = fig.add_subplot(gs[0, :]); draw_kpi_cards(ax_kpi, stats)
    ax_comp = fig.add_subplot(gs[1, 0]); plot_completion_rate(ax_comp, stats)
    ax_guard = fig.add_subplot(gs[1, 1]); plot_guardrails(ax_guard, data)
    ax_drop = fig.add_subplot(gs[2, 0]); plot_step_dropoff(ax_drop, data)
    ax_trend = fig.add_subplot(gs[2, 1]); plot_daily_trend(ax_trend, data)
    ax_rec = fig.add_subplot(gs[3, :]); draw_recommendation(ax_rec, stats)

    fig.savefig(OUT_DIR / "dashboard.png", dpi=160, facecolor="white")
    plt.close(fig)
    print(f"Wrote {OUT_DIR / 'dashboard.png'}")


def build_individual_charts(data):
    stats = data["stats"]
    specs = [
        ("completion_rate.png", lambda ax: plot_completion_rate(ax, stats)),
        ("guardrails.png", lambda ax: plot_guardrails(ax, data)),
        ("step_dropoff.png", lambda ax: plot_step_dropoff(ax, data)),
        ("daily_trend.png", lambda ax: plot_daily_trend(ax, data)),
    ]
    for filename, plot_fn in specs:
        fig, ax = plt.subplots(figsize=(8, 5))
        plot_fn(ax)
        fig.tight_layout()
        fig.savefig(CHART_DIR / filename, dpi=180, facecolor="white")
        plt.close(fig)
        print(f"Wrote {CHART_DIR / filename}")


if __name__ == "__main__":
    data = load_data()
    build_composite(data)
    build_individual_charts(data)
