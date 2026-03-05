#!/usr/bin/env python3
"""Refresh summary.json freshness fields each pipeline run."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default="summary.json")
    ap.add_argument("--reports-dir", default="reports")
    args = ap.parse_args()

    p = Path(args.summary)
    if p.exists():
        doc = json.loads(p.read_text(encoding="utf-8"))
    else:
        doc = {
            "macro": "Pipeline refresh complete.",
            "policy": "No policy summary available.",
            "delta": "Automated refresh.",
            "latestReportPath": "./reports/",
        }

    reports = sorted([x.name for x in Path(args.reports_dir).glob("20*.html")])
    if reports:
        doc["latestReportPath"] = f"./reports/{reports[-1]}"

    hkt = timezone(timedelta(hours=8))
    doc["updatedAt"] = datetime.now(hkt).replace(microsecond=0).isoformat()

    p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
