"""
Renders captured terminal output (real stdout from actual pipeline runs,
not fabricated) as styled "terminal window" PNG images -- a macOS-style
title bar plus syntax-colored monospace text -- for use as execution
evidence in the Assignment 3 report.

Usage:
    python render_terminal_screenshots.py
"""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
OUT_DIR = HERE / "evidence"
OUT_DIR.mkdir(exist_ok=True)

FONT_PATH_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]
FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
]

def find_font(candidates, size):
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()

FONT_SIZE = 15
FONT = find_font(FONT_PATH_CANDIDATES, FONT_SIZE)
FONT_BOLD = find_font(FONT_BOLD_CANDIDATES, FONT_SIZE) if any(Path(c).exists() for c in FONT_BOLD_CANDIDATES) else FONT

BG = (30, 32, 38)
TITLEBAR = (44, 47, 56)
FG_DEFAULT = (214, 219, 227)
FG_INFO = (110, 190, 255)
FG_WARNING = (240, 190, 90)
FG_CRITICAL = (240, 100, 100)
FG_MUTED = (140, 148, 160)
FG_GREEN = (110, 220, 140)
FG_HEADER = (200, 210, 225)

LINE_H = 21
PAD_X = 20
PAD_TOP = 46
PAD_BOTTOM = 18
CHAR_W = 9  # approx monospace advance for wrapping


def color_for_line(line: str):
    if "CRITICAL" in line or "FAILED" in line or "ALERT" in line or "/!\\" in line:
        return FG_CRITICAL
    if "WARNING" in line:
        return FG_WARNING
    if "SUCCEEDED" in line or "succeeded" in line or "status: success" in line:
        return FG_GREEN
    if "INFO" in line:
        return FG_INFO
    if line.startswith("---") or line.startswith("==="):
        return FG_HEADER
    if line.strip().startswith(("Run ID", "-" * 5)):
        return FG_MUTED
    return FG_DEFAULT


def wrap_line(line, max_chars):
    if len(line) <= max_chars:
        return [line]
    out = []
    while len(line) > max_chars:
        out.append(line[:max_chars])
        line = "    " + line[max_chars:]
    out.append(line)
    return out


def render(title: str, text: str, out_name: str, width: int = 1560, max_lines: int = None):
    lines = text.rstrip("\n").split("\n")
    if max_lines:
        lines = lines[:max_lines]
    max_chars = (width - 2 * PAD_X) // CHAR_W
    wrapped = []
    for ln in lines:
        wrapped.extend(wrap_line(ln, max_chars))

    height = PAD_TOP + len(wrapped) * LINE_H + PAD_BOTTOM
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    # title bar
    draw.rectangle([0, 0, width, 34], fill=TITLEBAR)
    for i, c in enumerate([(237, 106, 94), (245, 191, 79), (97, 194, 84)]):
        draw.ellipse([16 + i * 22, 12, 16 + i * 22 + 12, 24], fill=c)
    draw.text((width / 2, 17), title, font=FONT_BOLD, fill=FG_MUTED, anchor="mm")

    y = PAD_TOP
    for ln in wrapped:
        draw.text((PAD_X, y), ln, font=FONT, fill=color_for_line(ln))
        y += LINE_H

    img.save(OUT_DIR / out_name)
    print(f"Wrote {OUT_DIR / out_name} ({width}x{height}, {len(wrapped)} lines)")


def clean_capture(path):
    text = Path(path).read_text()
    # strip ANSI codes if any slipped through
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return text


if __name__ == "__main__":
    jobs = [
        ("assignment3 % python3 pipeline_runner.py", "/tmp/capture_normal.txt", "01_normal_run.png", None),
        ("assignment3 % python3 pipeline_runner.py --simulate transient-then-ok", "/tmp/capture_retry_ok.txt", "02_retry_then_succeed.png", None),
        ("assignment3 % python3 pipeline_runner.py --max-retries 3 --simulate always-transient", "/tmp/capture_retry_exhausted.txt", "03_retries_exhausted_alert.png", None),
        ("assignment3 % python3 pipeline_runner.py --simulate fatal-missing-file", "/tmp/capture_fatal.txt", "04_fatal_missing_file.png", None),
        ("assignment3 % python3 pipeline_runner.py --simulate bad-data", "/tmp/capture_baddata.txt", "05_fatal_validation_failure.png", None),
        ("assignment3 % python3 monitor.py --last 15", "/tmp/capture_monitor_final.txt", "06_monitor_health_summary.png", None),
        ("assignment3/scheduler % python3 scheduler_demo.py --demo-interval-seconds 4", "/tmp/capture_scheduler.txt", "07_scheduler_live_fire.png", 22),
    ]
    for title, capture_path, out_name, max_lines in jobs:
        render(title, clean_capture(capture_path), out_name, max_lines=max_lines)
