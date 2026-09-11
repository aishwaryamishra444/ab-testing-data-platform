"""
Builds a single, self-contained dashboard.html: KPI cards, statistical
test results, and interactive Plotly charts (completion rate with CIs,
guardrails, step drop-off funnel, daily trend), all populated from
dashboard_data.json. Plotly.js is embedded inline (not loaded from a
CDN), so the file opens and works fully offline -- double-click it, no
server, no internet connection required.

Usage:
    python dashboard/build_dashboard.py
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
PLOTLY_JS_PATH = Path("/usr/local/lib/python3.12/dist-packages/plotly/package_data/plotly.min.js")

ARM_COLORS = {"A": "#7a3b3b", "B": "#3a5a80", "C": "#10243e"}
ARM_LABELS = {"A": "A \u2014 Control (13 steps)", "B": "B \u2014 Medium (7 steps)", "C": "C \u2014 Short (5 steps)"}


def load_data():
    with open(HERE / "dashboard_data.json") as f:
        return json.load(f)


def build_html(data):
    plotly_js = PLOTLY_JS_PATH.read_text()
    stats = data["stats"]
    kpi = {r["test_group"]: r for r in data["kpi_by_group"]}
    guard = {r["test_group"]: r for r in data["guardrails_by_group"]}
    primary = stats["primary_metric"]
    srm = stats["srm_check"]
    rec = stats["recommendation"]
    power = stats["power_recheck"]

    data_json = json.dumps(data)

    kpi_cards = "".join(f"""
    <div class="kpi-card" style="border-top-color:{ARM_COLORS[arm]}">
      <div class="kpi-arm">{ARM_LABELS[arm]}</div>
      <div class="kpi-value">{kpi[arm]['onboarding_completion_rate']*100:.1f}%</div>
      <div class="kpi-sub">completion rate &middot; n={kpi[arm]['users_started']:,}</div>
      <div class="kpi-ci">95% CI [{primary['per_arm'][arm]['ci_95_low']*100:.1f}%, {primary['per_arm'][arm]['ci_95_high']*100:.1f}%]</div>
    </div>""" for arm in ["A", "B", "C"])

    test_rows = "".join(f"""
    <tr>
      <td>{t['label']}</td>
      <td>{t['absolute_diff']*100:+.1f} pp</td>
      <td>{t['relative_lift_pct']:+.1f}%</td>
      <td>[{t['diff_ci_95'][0]*100:+.1f}, {t['diff_ci_95'][1]*100:+.1f}] pp</td>
      <td>{'&lt;0.0001' if t['p_value'] < 0.0001 else f"{t['p_value']:.4f}"}</td>
      <td><span class="badge {'badge-sig' if t['significant_at_05'] else 'badge-nsig'}">
        {'Significant' if t['significant_at_05'] else 'Not significant'}</span></td>
    </tr>""" for t in primary["pairwise_tests"])

    guardrail_metric_labels = {
        "avg_lesson_relevance_score": ("Lesson relevance score (1-5)", "{:.2f}"),
        "refund_rate": ("Refund rate", "{:.1%}"),
        "cancellation_rate": ("Cancellation rate", "{:.1%}"),
        "support_ticket_rate": ("Support-ticket rate", "{:.1%}"),
        "notification_optin_rate": ("Notification opt-in rate", "{:.1%}"),
    }
    guardrail_rows = ""
    for m, (label, fmt) in guardrail_metric_labels.items():
        vals = "".join(f"<td>{fmt.format(guard[arm][m]) if guard[arm][m] is not None else '—'}</td>" for arm in ["A", "B", "C"])
        guardrail_rows += f"<tr><td>{label}</td>{vals}</tr>"

    flags_html = "".join(f"<li>{f}</li>" for f in stats["guardrail_metrics"]["regression_flags_vs_control"]) or "<li>None detected.</li>"

    verdict_class = "verdict-ship" if rec["verdict"].startswith("SHIP (") else "verdict-mitigate" if "MITIGATION" in rec["verdict"] else "verdict-hold"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Onboarding A/B Test — Experiment Evaluation Dashboard</title>
<style>
  :root {{
    --navy: #10243e; --midblue: #3a5a80; --lightbg: #f4f7fa; --border: #d7dee6;
    --a: #7a3b3b; --b: #3a5a80; --c: #10243e; --green: #2f6b3f; --amber: #7a5a1e; --red: #7a3b3b;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: Georgia, 'Times New Roman', serif; margin: 0; padding: 0;
    background: #fff; color: #1a1a1a; line-height: 1.5;
  }}
  header {{
    background: var(--navy); color: #fff; padding: 28px 40px;
  }}
  header h1 {{ margin: 0 0 4px 0; font-size: 26px; }}
  header p {{ margin: 0; color: #b9c8dc; font-style: italic; font-size: 14px; }}
  main {{ max-width: 1180px; margin: 0 auto; padding: 30px 24px 60px; }}
  h2 {{ color: var(--navy); border-bottom: 2px solid var(--navy); padding-bottom: 6px; margin-top: 46px; }}
  h3 {{ color: var(--midblue); }}
  .srm-banner {{
    background: #eaf5ee; border: 1.5px solid var(--green); color: #1c4a28;
    padding: 12px 18px; border-radius: 6px; margin: 18px 0; font-size: 14.5px;
  }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 18px; }}
  .kpi-card {{
    background: var(--lightbg); border-top: 5px solid; border-radius: 8px; padding: 18px 20px;
  }}
  .kpi-arm {{ font-size: 13px; color: #444; font-weight: bold; }}
  .kpi-value {{ font-size: 34px; font-weight: bold; color: var(--navy); margin: 6px 0 2px; }}
  .kpi-sub {{ font-size: 12.5px; color: #666; }}
  .kpi-ci {{ font-size: 11.5px; color: #888; margin-top: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 14px 0; font-size: 14px; }}
  th {{ background: var(--navy); color: #fff; text-align: left; padding: 8px 10px; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid var(--border); }}
  tr:nth-child(even) td {{ background: #f8fafb; }}
  .badge {{ padding: 3px 9px; border-radius: 10px; font-size: 12px; font-weight: bold; }}
  .badge-sig {{ background: #dcf0e1; color: var(--green); }}
  .badge-nsig {{ background: #f0e3d5; color: var(--amber); }}
  .chart {{ margin: 22px 0; }}
  .verdict-box {{
    border-radius: 8px; padding: 22px 26px; margin: 20px 0; border-left: 8px solid;
  }}
  .verdict-ship {{ background: #eaf5ee; border-color: var(--green); }}
  .verdict-mitigate {{ background: #fbf1e0; border-color: var(--amber); }}
  .verdict-hold {{ background: #f8e9e9; border-color: var(--red); }}
  .verdict-title {{ font-size: 20px; font-weight: bold; margin-bottom: 8px; }}
  .verdict-ship .verdict-title {{ color: var(--green); }}
  .verdict-mitigate .verdict-title {{ color: var(--amber); }}
  .verdict-hold .verdict-title {{ color: var(--red); }}
  .flags-list {{ background: var(--lightbg); border-radius: 6px; padding: 14px 24px; font-size: 14px; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  footer {{ text-align: center; color: #999; font-size: 12px; margin: 50px 0 20px; }}
  @media (max-width: 850px) {{ .kpi-grid, .grid-2 {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<header>
  <h1>Onboarding Flow Optimization &mdash; Experiment Evaluation Dashboard</h1>
  <p>3-arm A/B test (13 / 7 / 5 onboarding steps) &middot; Assignment 4 &middot; Aishwarya Mishra, USN 2648610, MSc Computational Statistics &amp; Applied AI, Christ University</p>
</header>
<main>

  <h2>Sample Ratio Mismatch Check</h2>
  <div class="srm-banner">
    Observed allocation: A={srm['observed']['A']:,}, B={srm['observed']['B']:,}, C={srm['observed']['C']:,}
    (expected ~{srm['expected_per_arm']:,.0f} each) &mdash; &chi;&sup2;={srm['chi2_statistic']}, p={srm['p_value']}.
    <strong>{srm['interpretation']}</strong>
  </div>

  <h2>Primary Metric: Onboarding Completion Rate</h2>
  <div class="kpi-grid">{kpi_cards}</div>
  <div class="chart" id="chart-completion"></div>

  <h3>Statistical Testing (Pairwise Two-Proportion Z-Tests)</h3>
  <table>
    <tr><th>Comparison</th><th>Absolute Diff</th><th>Relative Lift</th><th>95% CI (diff)</th><th>p-value</th><th>Result</th></tr>
    {test_rows}
  </table>
  <p style="font-size:13.5px;color:#555">{power['interpretation']}</p>

  <h2>Guardrail Metrics (Directional, Not Independently Hypothesis-Tested)</h2>
  <table>
    <tr><th>Guardrail</th><th>A (Control)</th><th>B (Medium)</th><th>C (Short)</th></tr>
    {guardrail_rows}
  </table>
  <div class="flags-list">
    <strong>Regression flags, C vs. control (A):</strong>
    <ul>{flags_html}</ul>
  </div>
  <div class="chart" id="chart-guardrails"></div>

  <h2>Funnel Diagnostics</h2>
  <div class="grid-2">
    <div class="chart" id="chart-dropoff"></div>
    <div class="chart" id="chart-daily"></div>
  </div>

  <h2>Recommendation</h2>
  <div class="verdict-box {verdict_class}">
    <div class="verdict-title">{rec['verdict']}</div>
    <p>{rec['reasoning']}</p>
  </div>

  <footer>
    Generated from assignment2/db/ab_test.db via assignment4/analysis/stats_analysis.py
    and assignment4/dashboard/data_export.py &middot; Full methodology in 00_documentation.md
  </footer>
</main>

<script>{plotly_js}</script>
<script>
const DATA = {data_json};
const ARM_COLORS = {{A: "{ARM_COLORS['A']}", B: "{ARM_COLORS['B']}", C: "{ARM_COLORS['C']}"}};
const ARM_LABELS = {{A: "{ARM_LABELS['A']}", B: "{ARM_LABELS['B']}", C: "{ARM_LABELS['C']}"}};

// --- Completion rate bar chart with 95% CI error bars ---
(function() {{
  const arms = ["A", "B", "C"];
  const perArm = DATA.stats.primary_metric.per_arm;
  const y = arms.map(a => perArm[a].completion_rate * 100);
  const errPlus = arms.map(a => (perArm[a].ci_95_high - perArm[a].completion_rate) * 100);
  const errMinus = arms.map(a => (perArm[a].completion_rate - perArm[a].ci_95_low) * 100);
  Plotly.newPlot('chart-completion', [{{
    x: arms.map(a => ARM_LABELS[a]), y: y, type: 'bar',
    marker: {{color: arms.map(a => ARM_COLORS[a])}},
    error_y: {{type: 'data', symmetric: false, array: errPlus, arrayminus: errMinus, color: '#333'}},
    text: y.map(v => v.toFixed(1) + '%'), textposition: 'outside',
  }}], {{
    title: 'Onboarding Completion Rate by Arm (95% CI)', yaxis: {{title: 'Completion Rate (%)', range: [0, 95]}},
    font: {{family: 'Georgia, serif'}}, margin: {{t: 50}},
  }}, {{responsive: true}});
}})();

// --- Guardrails grouped bar (normalized to control=100 for comparability) ---
(function() {{
  const arms = ["A", "B", "C"];
  const gb = DATA.guardrails_by_group.reduce((m, r) => (m[r.test_group] = r, m), {{}});
  const metrics = [
    ['avg_lesson_relevance_score', 'Lesson Relevance (1-5)'],
    ['refund_rate', 'Refund Rate (%)'],
    ['support_ticket_rate', 'Support Tickets (%)'],
    ['notification_optin_rate', 'Notification Opt-in (%)'],
  ];
  const traces = arms.map(a => ({{
    x: metrics.map(m => m[1]),
    y: metrics.map(m => {{
      const v = gb[a][m[0]];
      return m[0] === 'avg_lesson_relevance_score' ? v : v * 100;
    }}),
    name: ARM_LABELS[a], type: 'bar', marker: {{color: ARM_COLORS[a]}},
  }}));
  Plotly.newPlot('chart-guardrails', traces, {{
    title: 'Guardrail Metrics by Arm', barmode: 'group',
    font: {{family: 'Georgia, serif'}}, margin: {{t: 50}},
  }}, {{responsive: true}});
}})();

// --- Step drop-off funnel (abandon rate by step, per arm) ---
(function() {{
  const arms = ["A", "B", "C"];
  const traces = arms.map(a => {{
    const rows = DATA.step_dropoff.filter(r => r.test_group === a);
    return {{
      x: rows.map(r => r.step_number), y: rows.map(r => r.step_abandon_rate * 100),
      name: ARM_LABELS[a], mode: 'lines+markers', line: {{color: ARM_COLORS[a]}},
      text: rows.map(r => r.step_name),
    }};
  }});
  Plotly.newPlot('chart-dropoff', traces, {{
    title: 'Step-Level Abandon Rate', xaxis: {{title: 'Step Number'}}, yaxis: {{title: 'Abandon Rate (%)'}},
    font: {{family: 'Georgia, serif'}}, margin: {{t: 50}},
  }}, {{responsive: true}});
}})();

// --- Daily completion-rate trend ---
(function() {{
  const arms = ["A", "B", "C"];
  const traces = arms.map(a => {{
    const rows = DATA.daily_funnel.filter(r => r.test_group === a);
    return {{
      x: rows.map(r => r.install_date), y: rows.map(r => r.onboarding_completion_rate * 100),
      name: ARM_LABELS[a], mode: 'lines', line: {{color: ARM_COLORS[a]}},
    }};
  }});
  Plotly.newPlot('chart-daily', traces, {{
    title: 'Daily Completion Rate Trend', xaxis: {{title: 'Install Date'}}, yaxis: {{title: 'Completion Rate (%)'}},
    font: {{family: 'Georgia, serif'}}, margin: {{t: 50}},
  }}, {{responsive: true}});
}})();
</script>
</body>
</html>
"""
    return html


if __name__ == "__main__":
    data = load_data()
    html = build_html(data)
    out_path = HERE / "dashboard.html"
    out_path.write_text(html)
    print(f"Wrote {out_path} ({len(html)/1e6:.1f} MB)")
