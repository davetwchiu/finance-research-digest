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
        "<li style='margin:10px 0'>"
        f"<a href='./{name}' style='color:#9bb8ff;text-decoration:none;font-weight:600'>{name.removesuffix('.html')}</a>"
        "</li>"
        for name in files
    )

    generated_at = datetime.now(HKT).replace(microsecond=0)
    latest_label = files[0].removesuffix('.html') if files else None
    freshness_note = (
        f"Latest report: <strong>{latest_label}</strong> · Archive rebuilt: <strong>{generated_at.isoformat()}</strong>"
        if latest_label
        else f"Archive rebuilt: <strong>{generated_at.isoformat()}</strong>"
    )
    latest_cta = (
        f"<a href='./{files[0]}' style='display:inline-block;text-decoration:none;color:#fff;background:linear-gradient(180deg,#5f87ff,#2f5bd3);font-weight:700;padding:10px 14px;border-radius:10px'>Open latest digest</a>"
        if files else ""
    )

    html = f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width,initial-scale=1'>
  <title>Atlas Daily Digest Archive</title>
  <style>
    body{{font-family:Inter,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:linear-gradient(180deg,#090e1d,#0c1330);color:#e8ecff;line-height:1.55}}
    .wrap{{max-width:960px;margin:0 auto;padding:24px}}
    .card{{background:#121936;border:1px solid #2a3768;border-radius:14px;padding:16px;margin:14px 0}}
    .muted{{color:#a7b0d6}}
    a{{color:#9bb8ff}}
    ul{{padding-left:20px}}
  </style>
</head>
<body>
  <div class='wrap'>
    <p><a href='../index.html'>← Back to Atlas</a></p>
    <div class='card'>
      <h1 style='margin:0 0 8px'>Atlas daily digest archive</h1>
      <p class='muted' style='margin:0 0 12px'>{freshness_note}</p>
      <p class='muted' style='margin:0 0 12px'>Use this archive to review the macro / policy / regime view day by day. The daily digest is meant to answer three questions quickly: what changed, what matters for positioning, and what would change the view.</p>
      {latest_cta}
    </div>
    <div class='card'>
      <h2 style='margin-top:0'>Available reports</h2>
      <ul>
        {items if items else '<li>No reports yet.</li>'}
      </ul>
    </div>
  </div>
</body>
</html>
"""

    (reports_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"Rebuilt reports/index.html ({len(files)} report files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
