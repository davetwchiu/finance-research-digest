#!/usr/bin/env python3
"""Publish-blocking QC for pilot ticker depth quality."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

PILOTS = ("NVDA", "PLTR", "TSLA")

REQUIRED_MARKERS = [
    "Deterministic verdict",
    "Technical block (real inputs)",
    "Fundamentals block (real inputs)",
    "Risk map",
    "Quality gate evidence",
    "Last generated (UTC)",
    "Last generated (HKT)",
]


def validate(path: Path, min_words: int) -> list[str]:
    txt = path.read_text(encoding="utf-8")
    errs: list[str] = []

    for marker in REQUIRED_MARKERS:
        if marker not in txt:
            errs.append(f"missing marker: {marker}")

    word_count = len(re.findall(r"[A-Za-z0-9_\-]+", txt))
    if word_count < min_words:
        errs.append(f"word_count {word_count} < min_words {min_words}")

    rows = txt.count("<tr>")
    if rows < 12:
        errs.append(f"table row count too low: {rows}")

    if not re.search(r"Total score:\s*<strong>\d+/100</strong>", txt):
        errs.append("missing deterministic total score line")

    if "N/A" in txt:
        errs.append("contains N/A placeholders")

    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description="QC depth gates for pilot ticker pages")
    ap.add_argument("--tickers-dir", default="tickers")
    ap.add_argument("--min-words", type=int, default=380)
    args = ap.parse_args()

    fails = 0
    for ticker in PILOTS:
        path = Path(args.tickers_dir) / f"{ticker}.html"
        if not path.exists():
            print(f"FAIL {ticker}: missing file {path}")
            fails += 1
            continue
        errs = validate(path, min_words=args.min_words)
        if errs:
            print(f"FAIL {ticker}: " + "; ".join(errs))
            fails += 1
        else:
            print(f"PASS {ticker}: depth QC passed")

    if fails:
        print(f"Depth QC FAILED: {fails} pilot page(s) blocked")
        return 1

    print("Depth QC PASSED: pilot pages meet publish thresholds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
