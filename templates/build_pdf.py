#!/usr/bin/env python3
"""
Builds styled, academic-quality PDF documentation from markdown sources
using pandoc (markdown -> standalone HTML) + weasyprint (HTML+CSS -> PDF,
for proper CSS paged-media support: running headers, page-number footers,
a dedicated cover page, and a generated table of contents).

Usage:
    python templates/build_pdf.py \
        --md assignment1/01_business_understanding.md assignment1/02_event_tracking_plan.md \
        --title "Assignment 1: Business Understanding, Event Design & Data Generation" \
        --subtitle "Onboarding Flow Optimization A/B Test" \
        --out docs/Assignment1_Documentation.pdf
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

from weasyprint import HTML

HERE = Path(__file__).parent
CSS_PATH = HERE / "style.css"


def build(md_paths, title, subtitle, author, date, out_path, repo_root):
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        html_path = Path(tmp.name)

    cmd = [
        "pandoc", *[str(p) for p in md_paths],
        "-o", str(html_path),
        "-t", "html5", "-s", "--toc", "--toc-depth=3",
        "-c", str(CSS_PATH),
        "--metadata", f"title={title}",
        "--metadata", f"subtitle={subtitle}",
        "--metadata", f"author={author}",
        "--metadata", f"date={date}",
        "--embed-resources", "--standalone",
    ]
    subprocess.run(cmd, check=True)

    HTML(str(html_path), base_url=str(repo_root)).write_pdf(str(out_path))
    html_path.unlink()
    print(f"Wrote {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--md", nargs="+", required=True, help="Markdown source file(s), in order")
    parser.add_argument("--title", required=True)
    parser.add_argument("--subtitle", required=True)
    parser.add_argument("--author", default="Aishwarya Mishra")
    parser.add_argument("--date", default="August 2026")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    repo_root = HERE.parent
    build(
        md_paths=[Path(p) for p in args.md],
        title=args.title,
        subtitle=args.subtitle,
        author=args.author,
        date=args.date,
        out_path=Path(args.out),
        repo_root=repo_root,
    )


if __name__ == "__main__":
    main()
