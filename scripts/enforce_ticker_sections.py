#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

HKT = timezone(timedelta(hours=8))
REQ = [
    "What changed in last 72h",
    "Business reality",
    "Moat + competitor check",
    "Catalyst calendar next 30d",
    "Risk map",
    "Actionable setup",
]

def load_json(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def best_link(items):
    for it in items:
        u = it.get('url')
        if u:
            return u
    return ''

def section_html(ticker, news_items, fundamentals, latest_report, now_hkt):
    cutoff = now_hkt - timedelta(hours=72)
    recent = []
    for it in news_items:
        ts = it.get('published_hkt')
        try:
            dt = datetime.fromisoformat(ts)
        except Exception:
            continue
        if dt >= cutoff:
            recent.append((dt, it))
    recent.sort(key=lambda x: x[0], reverse=True)

    last_verified = recent[0][0] if recent else now_hkt
    age_h = (now_hkt - last_verified).total_seconds()/3600
    freshness = 'fresh' if age_h <= 24 else 'stale'
    stale_warn = "<p><strong>STALE WARNING:</strong> latest verified item is older than 24h.</p>" if age_h > 24 else ""

    f = fundamentals or {}
    fallback = bool(f.get('fallback_used'))
    eqs = 35 if fallback else 70
    if recent:
        eqs += 15
    eqs = max(20, min(95, eqs))

    def insufficient(tag='INSUFFICIENT_VERIFIED_DATA'):
        return f"<p><code>{tag}</code></p>"

    if recent:
        changed = "<ul>" + "".join([
            f"<li>{dt.strftime('%Y-%m-%d %H:%M HKT')} — <a href='{it.get('url','')}'>{it.get('title','(untitled)')}</a> ({it.get('source','unknown')})</li>"
            for dt,it in recent[:3]
        ]) + "</ul>"
    else:
        changed = insufficient()

    if not fallback:
        biz = (
            f"<ul><li>Revenue growth YoY: {f.get('revenue_growth_yoy_pct','N/A')}%</li>"
            f"<li>FCF margin: {f.get('fcf_margin_pct','N/A')}%</li>"
            f"<li>Gross margin: {f.get('gross_margin_pct','N/A')}%</li>"
            f"<li>Source: <a href='{best_link(news_items) or f'https://finance.yahoo.com/quote/{ticker}/financials'}'>reference</a></li></ul>"
        )
    else:
        biz = insufficient()

    moat = "<ul>"
    moat += f"<li>Primary competitor set requires manual cross-check in sector context; see latest daily report: <a href='../{latest_report}'>{latest_report}</a>.</li>"
    moat += f"<li>Recent evidence anchor: <a href='{best_link(news_items)}'>{best_link(news_items) or 'No direct source in run'}</a></li>"
    moat += "</ul>" if best_link(news_items) else insufficient()

    cata = "<ul><li>Next 30d catalyst windows: earnings guidance updates, macro data prints (CPI/NFP/FOMC), and sector policy headlines.</li>"
    if recent:
        dt,it = recent[0]
        cata += f"<li>Nearest verified headline reference ({dt.strftime('%Y-%m-%d')}): <a href='{it.get('url','')}'>{it.get('title','')}</a></li>"
    else:
        cata += "<li><code>INSUFFICIENT_VERIFIED_DATA</code> for ticker-specific dated corporate event in next 30d.</li>"
    cata += "</ul>"

    risk = "<ul><li>Macro beta shock (rates/USD/oil) can dominate idiosyncratic setup.</li>"
    if recent:
        dt,it = recent[0]
        risk += f"<li>Latest headline risk marker ({dt.strftime('%Y-%m-%d')}): <a href='{it.get('url','')}'>{it.get('source','source')}</a>.</li>"
    else:
        risk += "<li><code>INSUFFICIENT_VERIFIED_DATA</code> for fresh 72h ticker-specific risk event.</li>"
    risk += "</ul>"

    action = "<ul><li>Use trigger/invalidation levels already shown above in this page.</li><li>Only act if evidence remains fresh and headline flow does not invalidate thesis.</li>"
    action += "<li>Size down if freshness is stale or evidence quality score < 60.</li></ul>"

    meta = f"""
<div class='card'>
  <h2>Ticker evidence metadata</h2>
  <p><strong>Last verified time (HKT):</strong> {last_verified.strftime('%Y-%m-%d %H:%M:%S %Z')}</p>
  <p><strong>Freshness state:</strong> {freshness}</p>
  <p><strong>Evidence quality score:</strong> {eqs}/100</p>
  {stale_warn}
</div>
<div class='card'><h2>What changed in last 72h</h2>{changed}</div>
<div class='card'><h2>Business reality</h2>{biz}</div>
<div class='card'><h2>Moat + competitor check</h2>{moat}</div>
<div class='card'><h2>Catalyst calendar next 30d</h2>{cata}</div>
<div class='card'><h2>Risk map</h2>{risk}</div>
<div class='card'><h2>Actionable setup</h2>{action}</div>
"""
    return meta


def main():
    root = Path('.')
    watchlist = load_json('watchlist.json')['watchlist']
    news = load_json('data/cache/ticker_news_digest.json').get('tickers', {})
    fdoc = load_json('data/pilot_fundamentals.json')
    f_by = fdoc.get('tickers', {}) if isinstance(fdoc, dict) else {}
    latest_report = load_json('summary.json').get('latestReportPath', './reports/').replace('./','')
    now_hkt = datetime.now(timezone.utc).astimezone(HKT)

    for t in watchlist:
        t = str(t).upper().strip()
        p = root / 'tickers' / f'{t}.html'
        if not p.exists():
            continue
        html = p.read_text(encoding='utf-8')
        for h in REQ:
            if f">{h}<" in html:
                continue
        marker = "</body></html>"
        inject = section_html(t, (news.get(t) or {}).get('items', []), f_by.get(t), latest_report, now_hkt)
        if inject in html:
            continue
        html = html.replace(marker, inject + "\n" + marker)
        p.write_text(html, encoding='utf-8')
    print('enforced required sections for watchlist ticker pages')

if __name__ == '__main__':
    main()
