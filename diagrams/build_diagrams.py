"""
Generates the data-architecture (pipeline flow) diagram as a standalone SVG.
Run: python diagrams/build_diagrams.py
"""
from pathlib import Path

HERE = Path(__file__).parent

NAVY = "#10243e"
BLUE = "#1c3a5e"
MIDBLUE = "#3a5a80"
LIGHTBLUE = "#c9d9ea"
PANEL = "#eef3f8"
WHITE = "#ffffff"
GREY = "#6b7685"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg_header(width, height):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="Georgia, \'Times New Roman\', serif">\n'
        f'<defs>\n'
        f'  <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">\n'
        f'    <path d="M0,0 L10,5 L0,10 z" fill="{NAVY}"/>\n'
        f'  </marker>\n'
        f'</defs>\n'
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{WHITE}"/>\n'
    )


def layer_band(x, y, w, h, label, color=PANEL, label_color=NAVY):
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{color}" stroke="{LIGHTBLUE}" stroke-width="1.5"/>\n'
        f'<text x="{x+16}" y="{y+26}" font-size="15" font-weight="700" fill="{label_color}" letter-spacing="0.5">{esc(label)}</text>\n'
    )


def box(x, y, w, h, title, subtitle="", fill=NAVY, text_color=WHITE, title_size=12.5, sub_size=9.5):
    out = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}"/>\n'
    lines = subtitle.split("\\n") if subtitle else []
    ty = y + h / 2 - (7 * len(lines) if lines else 0)
    out += f'<text x="{x + w/2}" y="{ty}" text-anchor="middle" font-size="{title_size}" font-weight="700" fill="{text_color}">{esc(title)}</text>\n'
    for i, line in enumerate(lines):
        out += f'<text x="{x + w/2}" y="{ty + 15 + i*13}" text-anchor="middle" font-size="{sub_size}" fill="{text_color}" opacity="0.85">{esc(line)}</text>\n'
    return out


def arrow(x1, y1, x2, y2, color=NAVY, width=2.2, dash=None):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" marker-end="url(#arrow)"{dash_attr}/>\n'


def label(x, y, text, size=10.5, color=GREY, anchor="middle", italic=True, weight="400"):
    style = f'font-style="italic" ' if italic else ""
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" fill="{color}" {style}font-weight="{weight}">{esc(text)}</text>\n'


# =====================================================================
# DIAGRAM 1: Data Architecture / Pipeline Flow
# =====================================================================
def build_pipeline_diagram():
    W, H = 980, 1010
    svg = svg_header(W, H)

    svg += f'<text x="{W/2}" y="42" text-anchor="middle" font-size="20" font-weight="700" fill="{NAVY}">Data Architecture: Event Stream to Analysis-Ready Marts</text>\n'
    svg += f'<text x="{W/2}" y="64" text-anchor="middle" font-size="11.5" fill="{GREY}" font-style="italic">Onboarding Flow Optimization A/B Test &#8212; Assignments 1 &amp; 2</text>\n'

    band_x, band_w = 60, W - 120

    # --- Source band ---
    y0 = 92
    svg += layer_band(band_x, y0, band_w, 90, "SOURCE  \u2014  Client / Simulated Event Stream (Assignment 1)")
    svg += box(band_x + 40, y0 + 40, 240, 40, "Mobile App SDK", "(production, out of scope)", fill=MIDBLUE)
    svg += box(band_x + 320, y0 + 40, 260, 40, "data_generator.py", "6,000 users -> ~125k events", fill=NAVY)
    svg += box(band_x + 620, y0 + 40, 250, 40, "event_schema.json + stepmap.json", "schema + step design", fill=MIDBLUE, title_size=9.8, sub_size=8.8)

    y1 = y0 + 90 + 34
    svg += arrow(band_x + band_w/2, y0 + 90, band_x + band_w/2, y1)

    # --- RAW ---
    svg += layer_band(band_x, y1, band_w, 110, "RAW  \u2014  schema/01_raw.sql")
    svg += box(band_x + 40, y1 + 46, 300, 46, "raw_events", "column-for-column CSV mirror\\nno casting, no filtering", fill=NAVY, sub_size=8.8)
    svg += label(band_x + 40 + 150, y1 + 100, "grain: 1 row per delivered event", size=9, anchor="middle")

    y2 = y1 + 110 + 34
    svg += arrow(band_x + band_w/2, y1 + 110, band_x + band_w/2, y2)
    svg += label(band_x + band_w/2 + 170, y1 + 110 + 17, "validate \u00b7 deduplicate(event_id) \u00b7 json_extract flatten", size=9.5, anchor="middle")

    # --- STAGING ---
    svg += layer_band(band_x, y2, band_w, 110, "STAGING  \u2014  schema/02_staging.sql")
    svg += box(band_x + 40, y2 + 46, 260, 46, "stg_events", "typed, deduplicated, validated", fill=NAVY)
    svg += box(band_x + 340, y2 + 46, 260, 46, "stg_events_rejects", "quarantined invalid rows", fill="#7a3b3b")

    y3 = y2 + 110 + 34
    svg += arrow(band_x + 170, y2 + 110, band_x + 170, y3)
    svg += label(band_x + 170 + 220, y2 + 110 + 17, "dimensional modelling (star schema)", size=9.5, anchor="middle")

    # --- WAREHOUSE ---
    svg += layer_band(band_x, y3, band_w, 190, "WAREHOUSE  \u2014  schema/03_warehouse.sql  (star schema)")
    fact_x, fact_y, fact_w, fact_h = band_x + 300, y3 + 100, 300, 60
    svg += box(fact_x, fact_y, fact_w, fact_h, "fact_user_funnel", "grain: 1 row per user  \u2014  primary analytical fact", fill=NAVY, title_size=13)

    dim_specs = [
        ("dim_user", band_x + 40, y3 + 46),
        ("dim_date", band_x + 40, y3 + 122),
        ("dim_step", band_x + 700, y3 + 46),
    ]
    for name, dx, dy in dim_specs:
        svg += box(dx, dy, 170, 44, name, fill=MIDBLUE, title_size=11.5)
    # connectors dims -> fact
    svg += arrow(band_x + 40 + 170, y3 + 46 + 22, fact_x, fact_y + 12, color=MIDBLUE, width=1.6)
    svg += arrow(band_x + 40 + 170, y3 + 122 + 22, fact_x, fact_y + 48, color=MIDBLUE, width=1.6)
    svg += arrow(band_x + 700, y3 + 46 + 22, fact_x + fact_w, fact_y + 20, color=MIDBLUE, width=1.6)

    svg += box(band_x + 700, y3 + 122, 170, 44, "fact_onboarding_step_events", "grain: 1 row / step event", fill=NAVY, title_size=8.3, sub_size=7.8)
    svg += arrow(band_x + 700 + 85, y3 + 166, band_x + 700 + 85, y3 + 188, color=NAVY, width=1.6, dash="4,3")

    y4 = y3 + 190 + 34
    svg += arrow(band_x + band_w/2, y3 + 190, band_x + band_w/2, y4)
    svg += label(band_x + band_w/2 + 190, y3 + 190 + 17, "GROUP BY test_group  /  arm x step  /  date x arm", size=9.5, anchor="middle")

    # --- DATA MART ---
    svg += layer_band(band_x, y4, band_w, 110, "DATA MART  \u2014  schema/04_datamart.sql  (pre-aggregated, dashboard-ready)")
    mart_names = [
        ("mart_kpi_by_group", "1 row / arm"),
        ("mart_guardrails_by_group", "1 row / arm"),
        ("mart_step_dropoff", "1 row / arm x step"),
        ("mart_daily_funnel", "1 row / date x arm"),
    ]
    mw = (band_w - 80 - 3*20) / 4
    for i, (name, grain) in enumerate(mart_names):
        mx = band_x + 40 + i * (mw + 20)
        svg += box(mx, y4 + 46, mw, 46, name, grain, fill=NAVY, title_size=9.3, sub_size=8.2)

    y5 = y4 + 110 + 34
    svg += arrow(band_x + band_w/2, y4 + 110, band_x + band_w/2, y5)

    # --- CONSUMERS ---
    svg += layer_band(band_x, y5, band_w, 90, "CONSUMERS  \u2014  Assignments 3 & 4 (prospective)", color="#e8edf3")
    svg += box(band_x + 60, y5 + 40, 260, 40, "Orchestration + Monitoring", "scheduled rebuild, logging, alerts", fill=GREY)
    svg += box(band_x + 360, y5 + 40, 260, 40, "Dashboard", "KPI + guardrail visualization", fill=GREY)
    svg += box(band_x + 660, y5 + 40, 220, 40, "Statistical Test Suite", "z-test, SRM check", fill=GREY)

    svg += "</svg>"
    return svg, W, H


# =====================================================================
# DIAGRAM 2: Star Schema ERD
# =====================================================================
def build_erd_diagram():
    W, H = 980, 590
    svg = svg_header(W, H)
    svg += f'<text x="{W/2}" y="38" text-anchor="middle" font-size="19" font-weight="700" fill="{NAVY}">Warehouse Layer &#8212; Star Schema (Entity-Relationship Diagram)</text>\n'
    svg += f'<text x="{W/2}" y="59" text-anchor="middle" font-size="11" fill="{GREY}" font-style="italic">schema/03_warehouse.sql</text>\n'

    def table_box(x, y, w, title, rows, header_fill=NAVY):
        h = 34 + 20 * len(rows)
        out = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{WHITE}" stroke="{NAVY}" stroke-width="1.4"/>\n'
        out += f'<rect x="{x}" y="{y}" width="{w}" height="30" rx="6" fill="{header_fill}"/>\n'
        out += f'<rect x="{x}" y="{y+16}" width="{w}" height="14" fill="{header_fill}"/>\n'
        out += f'<text x="{x + w/2}" y="{y+21}" text-anchor="middle" font-size="11.5" font-weight="700" fill="{WHITE}">{esc(title)}</text>\n'
        for i, r in enumerate(rows):
            ry = y + 30 + 20 * i + 14
            key_marker = r[1] if len(r) > 1 else ""
            out += f'<text x="{x+10}" y="{ry}" font-size="9.5" fill="{BLUE}">{esc(r[0])}</text>\n'
            if key_marker:
                out += f'<text x="{x+w-10}" y="{ry}" text-anchor="end" font-size="8.5" fill="{MIDBLUE}" font-style="italic">{esc(key_marker)}</text>\n'
        return out, h

    # central fact
    fact_x, fact_y, fact_w = 390, 240, 220
    fact_rows = [
        ("user_id", "PK"), ("test_group", ""), ("platform", ""),
        ("completed_onboarding", ""), ("activated", ""), ("purchased", ""),
        ("returned_day30", ""), ("avg_relevance_score", ""),
    ]
    fact_svg, fact_h = table_box(fact_x, fact_y, fact_w, "fact_user_funnel", fact_rows)
    svg += fact_svg

    # dims around it
    dim_user_rows = [("user_id", "PK"), ("test_group", ""), ("platform", ""), ("install_date", ""), ("signup_method", "")]
    dim_user_svg, dim_user_h = table_box(60, 120, 200, "dim_user", dim_user_rows, header_fill=MIDBLUE)
    svg += dim_user_svg

    dim_date_rows = [("date_key", "PK"), ("year", ""), ("month", ""), ("day_of_week", ""), ("is_weekend", "")]
    dim_date_svg, dim_date_h = table_box(60, 380, 200, "dim_date", dim_date_rows, header_fill=MIDBLUE)
    svg += dim_date_svg

    dim_step_rows = [("test_group", "PK"), ("step_number", "PK"), ("step_name", ""), ("step_bucket", "")]
    dim_step_svg, dim_step_h = table_box(720, 120, 200, "dim_step", dim_step_rows, header_fill=MIDBLUE)
    svg += dim_step_svg

    fact2_rows = [("event_id", "PK"), ("user_id", "FK"), ("test_group", ""), ("step_number", ""), ("step_event_type", ""), ("event_timestamp", "")]
    fact2_svg, fact2_h = table_box(720, 360, 220, "fact_onboarding_step_events", fact2_rows)
    svg += fact2_svg

    # relationship lines
    svg += f'<line x1="260" y1="{120+dim_user_h/2}" x2="{fact_x}" y2="{fact_y+40}" stroke="{MIDBLUE}" stroke-width="1.6"/>\n'
    svg += label(300, 175, "1", size=10, italic=False, anchor="middle")
    svg += label(fact_x-24, fact_y+34, "N", size=10, italic=False, anchor="middle")

    svg += f'<line x1="260" y1="{380+dim_date_h/2}" x2="{fact_x}" y2="{fact_y+fact_h-30}" stroke="{MIDBLUE}" stroke-width="1.6"/>\n'
    svg += label(300, 420, "1", size=10, italic=False, anchor="middle")

    svg += f'<line x1="720" y1="{120+dim_step_h/2}" x2="{fact_x+fact_w}" y2="{fact_y+60}" stroke="{MIDBLUE}" stroke-width="1.6"/>\n'
    svg += label(690, 175, "1", size=10, italic=False, anchor="middle")

    svg += f'<line x1="720" y1="{360+30}" x2="{fact_x+fact_w}" y2="{fact_y+fact_h-40}" stroke="{NAVY}" stroke-width="1.6" stroke-dasharray="4,3"/>\n'
    svg += label(690, 400, "same grain (user_id)", size=8, italic=True, anchor="middle")

    svg += f'<line x1="830" y1="{120+dim_step_h}" x2="830" y2="360" stroke="{MIDBLUE}" stroke-width="1.6"/>\n'
    svg += label(870, 260, "1", size=10, italic=False, anchor="middle")

    # legend
    svg += f'<rect x="60" y="560" width="14" height="14" fill="{MIDBLUE}"/>\n'
    svg += label(240, 572, "Dimension table (descriptive attributes)", size=9.5, anchor="start")
    svg += f'<rect x="500" y="560" width="14" height="14" fill="{NAVY}"/>\n'
    svg += label(680, 572, "Fact table (measures / observed events)", size=9.5, anchor="start")

    svg += "</svg>"
    return svg, W, H


# =====================================================================
# DIAGRAM 3: Experiment / User Journey Flow
# =====================================================================
def build_journey_diagram():
    W, H = 980, 640
    svg = svg_header(W, H)
    svg += f'<text x="{W/2}" y="36" text-anchor="middle" font-size="19" font-weight="700" fill="{NAVY}">Experiment Flow: Randomization to Outcome</text>\n'
    svg += f'<text x="{W/2}" y="57" text-anchor="middle" font-size="11" fill="{GREY}" font-style="italic">User journey across the three onboarding arms (event names shown are those actually emitted)</text>\n'

    cx = W / 2
    svg += box(cx-110, 78, 220, 44, "app_installed", "user_id minted", fill=NAVY)
    svg += arrow(cx, 122, cx, 158)
    svg += box(cx-140, 158, 280, 44, "onboarding_started", "arm randomized: A / B / C (~33% each)", fill=NAVY, sub_size=8.5)

    y_split = 202
    svg += arrow(cx, y_split+44, cx-320, y_split+90)
    svg += arrow(cx, y_split+44, cx, y_split+90)
    svg += arrow(cx, y_split+44, cx+320, y_split+90)

    arm_y = y_split + 90
    arms = [
        ("Arm A \u2014 Control", "13 steps", cx-320, "#7a3b3b"),
        ("Arm B \u2014 Medium", "7 steps", cx, MIDBLUE),
        ("Arm C \u2014 Short", "5 steps", cx+320, NAVY),
    ]
    for title, sub, ax, color in arms:
        svg += box(ax-110, arm_y, 220, 44, title, sub, fill=color)

    y_steps = arm_y + 44 + 30
    svg += label(cx, y_steps, "onboarding_step_viewed  \u2192  _completed  |  _abandoned (exits funnel)", size=9.5)
    for _, _, ax, _ in arms:
        svg += arrow(ax, arm_y+44, ax, y_steps+14)

    y_complete = y_steps + 50
    for _, _, ax, color in arms:
        svg += arrow(ax, y_steps+20, ax, y_complete)
        svg += box(ax-110, y_complete, 220, 40, "onboarding_completed", fill=color, title_size=10.5)

    y_conv = y_complete + 40 + 34
    svg += f'<line x1="{cx-320}" y1="{y_complete+40}" x2="{cx-40}" y2="{y_conv-8}" stroke="{GREY}" stroke-width="1.4"/>\n'
    svg += arrow(cx, y_complete+40, cx, y_conv-8, color=GREY, width=1.4)
    svg += f'<line x1="{cx+320}" y1="{y_complete+40}" x2="{cx+40}" y2="{y_conv-8}" stroke="{GREY}" stroke-width="1.4"/>\n'
    svg += label(cx, y_conv-14, "funnel outcomes converge for downstream analysis", size=9, color=GREY)

    stages = [
        ("first_lesson_completed", "activation"),
        ("app_opened_day1/7/30", "retention"),
        ("subscription_purchased", "paid conversion"),
    ]
    sw = 260
    total = sw*3 + 40*2
    sx0 = cx - total/2
    for i, (name, tag) in enumerate(stages):
        sx = sx0 + i*(sw+40)
        svg += box(sx, y_conv, sw, 46, name, tag, fill=NAVY, sub_size=9)
        if i > 0:
            svg += arrow(sx-40, y_conv+23, sx, y_conv+23)

    svg += label(cx, y_conv+80, "Guardrails (lesson relevance, refund rate, support tickets, notification opt-in) are measured", size=9.5, color=GREY)
    svg += label(cx, y_conv+96, "across every stage above and reported per arm \u2014 see 01_business_understanding.md Section 4.3", size=9.5, color=GREY)

    svg += "</svg>"
    return svg, W, H


if __name__ == "__main__":
    import cairosvg

    for build_fn, filename in [
        (build_pipeline_diagram, "data_architecture.svg"),
        (build_erd_diagram, "star_schema_erd.svg"),
        (build_journey_diagram, "experiment_flow.svg"),
    ]:
        svg, w, h = build_fn()
        out_path = HERE / filename
        out_path.write_text(svg)
        print(f"Wrote {out_path} ({w}x{h})")

        # Also rasterize a high-res PNG counterpart: weasyprint's built-in
        # SVG renderer has a text-anchor/clipping bug that truncates some
        # <text> content, so the PDF build pipeline embeds these PNGs
        # instead, while README.md / GitHub keep using the crisp SVGs.
        png_path = HERE / (Path(filename).stem + ".png")
        cairosvg.svg2png(url=str(out_path), write_to=str(png_path), scale=2.5)
        print(f"Wrote {png_path}")
