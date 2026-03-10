#!/usr/bin/env python3
"""Rebuild reports/index.html from available daily report files."""

from __future__ import annotations

from pathlib import Path
import re
from datetime import datetime, timedelta, timezone


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.html$")
HKT = timezone(timedelta(hours=8))


def main() -> int:
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    files = [p.name for p in reports_dir.iterdir() if p.is_file() and DATE_RE.match(p.name)]
    files.sort(reverse=True)

    items = "\n".join(
        f"<li><a href='./{name}'>{name.removesuffix('.html')}</a></li>" for name in files
    )

    generated_at = datetime.now(HKT).replace(microsecond=0)
    latest_label = files[0].removesuffix('.html') if files else None
    freshness_note = (
        f"Latest report: <strong>{latest_label}</strong> · Archive rebuilt: <strong>{generated_at.isoformat()}</strong>"
        if latest_label
        else f"Archive rebuilt: <strong>{generated_at.isoformat()}</strong>"
    )

    html = (
        "<!doctype html><html><body style='font-family:Inter,-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;line-height:1.45'>"
        "<h1>Reports</h1>"
        f"<p style='color:#4b5563'>{freshness_note}</p>"
        "<ul>"
        + (items if items else "<li>No reports yet.</li>")
        + "</ul></body></html>\n"
    )

    (reports_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"Rebuilt reports/index.html ({len(files)} report files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
