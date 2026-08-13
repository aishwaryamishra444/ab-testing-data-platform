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
import re
import subprocess
import tempfile
from pathlib import Path

from weasyprint import HTML

HERE = Path(__file__).parent
CSS_PATH = HERE / "style.css"


def build(md_paths, title, subtitle, author, out_path, repo_root):
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        html_path = Path(tmp.name)

    md_paths = [p.resolve() for p in md_paths]
    out_path = out_path.resolve()
    pandoc_cwd = md_paths[0].parent

    # weasyprint's built-in SVG renderer has a text-anchor/clipping bug that
    # truncates some <text> content inside our diagrams. diagrams/build_diagrams.py
    # also emits a rasterized .png counterpart of every .svg specifically for
    # this reason. Feed pandoc temp copies of the markdown with image
    # references swapped to .png, so --embed-resources base64-embeds the
    # PNG instead of the SVG. README.md / GitHub keep using the crisp .svg
    # files directly (this substitution only touches the PDF build's temp copy).
    temp_md_paths = []
    for p in md_paths:
        text = p.read_text()
        text = re.sub(r'(!\[[^\]]*\]\([^)]+)\.svg\)', r'\1.png)', text)
        temp_p = p.with_name(f".{p.stem}.pdfbuild.md")
        temp_p.write_text(text)
        temp_md_paths.append(temp_p)

    cmd = [
        "pandoc", *[str(p) for p in temp_md_paths],
        "-o", str(html_path),
        "-t", "html5", "-s", "--toc", "--toc-depth=3",
        "-c", str(CSS_PATH.resolve()),
        "--metadata", f"title={title}",
        "--metadata", f"subtitle={subtitle}",
        "--metadata", f"author={author}",
        "--embed-resources", "--standalone",
    ]
    try:
        subprocess.run(cmd, check=True, cwd=pandoc_cwd)
    finally:
        for p in temp_md_paths:
            p.unlink(missing_ok=True)

    HTML(str(html_path), base_url=str(repo_root)).write_pdf(str(out_path))
    html_path.unlink()
    print(f"Wrote {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--md", nargs="+", required=True, help="Markdown source file(s), in order")
    parser.add_argument("--title", required=True)
    parser.add_argument("--subtitle", required=True)
    parser.add_argument("--author", default="Aishwarya Mishra | USN 2648610 | MSc Computational Statistics & Applied AI, Christ University")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    repo_root = HERE.parent
    build(
        md_paths=[Path(p) for p in args.md],
        title=args.title,
        subtitle=args.subtitle,
        author=args.author,
        out_path=Path(args.out),
        repo_root=repo_root,
    )


if __name__ == "__main__":
    main()
