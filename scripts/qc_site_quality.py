#!/usr/bin/env python3
"""Site-level quality guardrails for investment-intelligence pages."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _load_watchlist(path: Path) -> list[str]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    wl = doc.get("watchlist") if isinstance(doc, dict) else None
    if not isinstance(wl, list) or not wl:
        raise ValueError(f"Invalid watchlist: {path}")
    return [str(x).strip().upper() for x in wl if str(x).strip()]


def _latest_daily_report(reports_dir: Path) -> Path | None:
    files = sorted([p for p in reports_dir.glob("20*.html")])
    return files[-1] if files else None


def _fallback_count(tickers_dir: Path, tickers: list[str]) -> int:
    n = 0
    for t in tickers:
        p = tickers_dir / f"{t}.html"
        if not p.exists():
            continue
        s = p.read_text(encoding="utf-8", errors="ignore")
        if "Fallback fundamentals used: Yes" in s:
            n += 1
    return n


def _has_stale_phrase(index_html: Path) -> bool:
    s = index_html.read_text(encoding="utf-8", errors="ignore")
    return "Daily Finance Research Digest" in s


def _report_has_repeated_regime(report_html: Path) -> bool:
    s = report_html.read_text(encoding="utf-8", errors="ignore")
    # Catch repeated templated nodes like "Regime node X" blocks.
    return len(re.findall(r"Regime node\s+\d+", s, flags=re.IGNORECASE)) >= 5


def main() -> int:
    ap = argparse.ArgumentParser(description="Quality guard for site pages")
    ap.add_argument("--root", default=".")
    ap.add_argument("--max-fallback-ratio", type=float, default=0.9)
    args = ap.parse_args()

    root = Path(args.root)
    watchlist = _load_watchlist(root / "watchlist.json")
    tickers_dir = root / "tickers"
    reports_dir = root / "reports"
    index_html = root / "index.html"

    fails: list[str] = []

    # Check ticker page coverage
    missing = [t for t in watchlist if not (tickers_dir / f"{t}.html").exists()]
    if missing:
        fails.append(f"missing ticker pages: {', '.join(missing)}")

    # Check fallback fundamentals ratio
    fallback_n = _fallback_count(tickers_dir, watchlist)
    ratio = fallback_n / max(1, len(watchlist))
    print(f"fallback fundamentals: {fallback_n}/{len(watchlist)} ({ratio:.0%})")
    if ratio > args.max_fallback_ratio:
        fails.append(
            f"fallback ratio {ratio:.0%} exceeds max {args.max_fallback_ratio:.0%}"
        )

    # Brand phrase hygiene
    if _has_stale_phrase(index_html):
        fails.append("index contains deprecated phrase 'Daily Finance Research Digest'")

    latest = _latest_daily_report(reports_dir)
    if latest is None:
        fails.append("missing daily report html")
    else:
        print(f"latest report: {latest.name}")
        if _report_has_repeated_regime(latest):
            fails.append(f"{latest.name} contains repeated 'Regime node' boilerplate")

    if fails:
        print("SITE_QC_FAIL")
        for f in fails:
            print(" -", f)
        return 2

    print("SITE_QC_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
