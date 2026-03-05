#!/usr/bin/env python3
"""Publish-blocking QC for ticker depth quality (full watchlist)."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REQUIRED_MARKERS = [
    "Deterministic verdict",
    "News pulse (price-impact view)",
    "Decision gate (before adding risk)",
    "Technical block (real inputs)",
    "Fundamentals block (real inputs)",
    "Risk map",
    "Quality gate evidence",
    "Last generated (UTC)",
    "Last generated (HKT)",
]


def _load_watchlist(path: str) -> list[str]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    wl = doc.get("watchlist") if isinstance(doc, dict) else None
    if not isinstance(wl, list) or not wl:
        raise ValueError(f"Invalid or empty watchlist in {path}")
    return [str(x).strip().upper() for x in wl if str(x).strip()]


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

    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description="QC depth gates for ticker pages")
    ap.add_argument("--tickers-dir", default="tickers")
    ap.add_argument("--watchlist", default="watchlist.json")
    ap.add_argument("--min-words", type=int, default=380)
    args = ap.parse_args()

    watchlist = _load_watchlist(args.watchlist)
    fails = 0
    for ticker in watchlist:
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
        print(f"Depth QC FAILED: {fails} ticker page(s) blocked")
        return 1

    print("Depth QC PASSED: all watchlist ticker pages meet publish thresholds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
