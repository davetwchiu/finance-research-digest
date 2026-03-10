#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import ssl
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any

HKT = timezone(timedelta(hours=8))
UTC = timezone.utc
UA = "AtlasMarketIntelligence/1.0 david@example.com"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
TARGET_FORMS = {"10-K", "10-Q", "8-K"}


def fetch_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_watchlist(path: Path) -> list[str]:
    doc = json.loads(path.read_text())
    return [str(x).strip().upper() for x in doc.get("watchlist", []) if str(x).strip()]


def cik_map() -> dict[str, dict[str, Any]]:
    doc = fetch_json(SEC_TICKERS_URL)
    data = doc.get("data", []) if isinstance(doc, dict) else []
    out: dict[str, dict[str, Any]] = {}
    for row in data:
        if len(row) >= 3:
            cik, name, ticker = row[0], row[1], str(row[2]).upper()
            out[ticker] = {"cik": str(cik).zfill(10), "name": name}
    return out


def accession_no_dashes(acc: str) -> str:
    return acc.replace("-", "")


def filing_url(cik: str, accession: str, primary_doc: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_no_dashes(accession)}/{primary_doc}"


def filing_index_url(cik: str, accession: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_no_dashes(accession)}/"


def summarize_filing(ticker: str, form: str, filing_date: str) -> tuple[str, str, str, str]:
    date_obj = datetime.fromisoformat(filing_date).date()
    age = (datetime.now(HKT).date() - date_obj).days
    if form == "10-K":
        exec_summary = f"{ticker} filed a 10-K on {filing_date}, which means the company published its full annual report. This is usually the best place to check whether the business actually improved, whether management is sounding more cautious, and whether risks got worse."
        layman = "Think of a 10-K as the company’s yearly health check: business performance, major risks, what changed strategically, and whether the story still matches reality."
        details = "Read the 10-K for changes in revenue mix, margins, customer concentration, debt/cash trends, risk factors, and management tone versus the prior year."
        why = "Annual filings matter because they often reveal slow-building problems or important strategic changes that don’t show up in headlines."
    elif form == "10-Q":
        exec_summary = f"{ticker} filed a 10-Q on {filing_date}, which is the quarterly operating update. This is where we check whether the last quarter actually strengthened or weakened the thesis."
        layman = "A 10-Q is the company’s quarter-by-quarter progress report: are sales, margins, cash flow, and risks moving in the right direction?"
        details = "Read the 10-Q for quarter-on-quarter and year-on-year shifts in revenue, gross margin, operating margin, liquidity, dilution/debt, and any changes in management discussion or disclosed risks."
        why = "Quarterly filings matter because they test whether the market story is real or just momentum and narrative."
    else:
        exec_summary = f"{ticker} filed an 8-K on {filing_date}. An 8-K usually means something happened that management considered important enough to disclose immediately."
        layman = "An 8-K is the company saying: something important just happened, and investors need to know now."
        details = "Read the 8-K for the actual trigger: earnings release, contract news, leadership changes, financing, acquisitions, legal issues, or guidance changes."
        why = "8-Ks matter because they often contain the first hard disclosure behind a price move or narrative shift."
    freshness = f"Filed {age} day(s) ago." if age >= 0 else f"Filed on {filing_date}."
    return exec_summary, layman, details, why + " " + freshness


def build_report(watchlist: list[str], out_root: Path) -> tuple[Path, dict[str, Any]]:
    mapping = cik_map()
    findings: list[dict[str, Any]] = []
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for ticker in watchlist:
        meta = mapping.get(ticker)
        if not meta:
            continue
        try:
            sub = fetch_json(SEC_SUBMISSIONS.format(cik=meta["cik"]))
        except Exception:
            continue
        recent = ((sub.get("filings") or {}).get("recent") or {})
        forms = recent.get("form", []) or []
        dates = recent.get("filingDate", []) or []
        accessions = recent.get("accessionNumber", []) or []
        primary_docs = recent.get("primaryDocument", []) or []
        for form, fdate, acc, pdoc in zip(forms, dates, accessions, primary_docs):
            if form not in TARGET_FORMS:
                continue
            if not fdate:
                continue
            dt = datetime.fromisoformat(fdate).replace(tzinfo=HKT)
            if dt.date() < (datetime.now(HKT).date() - timedelta(days=45)):
                continue
            exec_summary, layman, details, why = summarize_filing(ticker, form, fdate)
            item = {
                "ticker": ticker,
                "company": meta["name"],
                "form": form,
                "filingDate": fdate,
                "accession": acc,
                "primaryDoc": pdoc,
                "url": filing_url(meta["cik"], acc, pdoc),
                "indexUrl": filing_index_url(meta["cik"], acc),
                "executiveSummary": exec_summary,
                "laymanSummary": layman,
                "details": details,
                "whyItMatters": why,
            }
            findings.append(item)
            by_ticker[ticker].append(item)
            break

    findings.sort(key=lambda x: (x["filingDate"], x["ticker"]), reverse=True)
    stamp = datetime.now(HKT).replace(microsecond=0)
    date_label = stamp.date().isoformat()

    reports_dir = out_root / "reports" / "filings"
    reports_dir.mkdir(parents=True, exist_ok=True)
    archive_path = reports_dir / f"{date_label}.html"

    latest_path = "./reports/filings/" + archive_path.name
    count = len(findings)
    latest_summary = {
        "updatedAt": stamp.isoformat(),
        "count": count,
        "market": f"{count} recent SEC filing(s) matched the current watchlist in the last 45 days." if count else "No recent 10-Q, 10-K, or 8-K filings were found for the current watchlist in the last 45 days.",
        "tech": "This panel tracks hard company disclosures, not headlines. Use it to verify whether the business story actually changed.",
        "risk": "If a name has no recent filing here, that does not mean nothing happened — only that no target SEC form was found in the recent window.",
        "latestPath": latest_path,
    }

    top = findings[:5]
    exec_lines = "".join(
        f"<li><strong>{escape(x['ticker'])}</strong> — {escape(x['form'])} filed {escape(x['filingDate'])}. {escape(x['laymanSummary'])} <a href='{escape(x['url'])}'>SEC filing</a></li>"
        for x in top
    ) or "<li>No recent qualifying filings found in the current watchlist window.</li>"

    cards = []
    for item in findings:
        cards.append(
            f"<div class='card'><h2>{escape(item['ticker'])} — {escape(item['form'])}</h2>"
            f"<p class='muted'>Filed: {escape(item['filingDate'])} · Company: {escape(item['company'])}</p>"
            f"<p><strong>Executive summary:</strong> {escape(item['executiveSummary'])}</p>"
            f"<p><strong>Layman view:</strong> {escape(item['laymanSummary'])}</p>"
            f"<p><strong>What to read for:</strong> {escape(item['details'])}</p>"
            f"<p><strong>Why it matters:</strong> {escape(item['whyItMatters'])}</p>"
            f"<p><a href='{escape(item['url'])}'>Open primary filing</a> · <a href='{escape(item['indexUrl'])}'>SEC filing folder</a></p></div>"
        )

    html = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Atlas SEC Filings Watch — {date_label}</title>
<style>
body{{font-family:Georgia,'Iowan Old Style','Palatino Linotype',serif;margin:24px;background:linear-gradient(180deg,#0a1025,#0f1738);color:#edf2ff;line-height:1.68}}
a{{color:#9bb8ff}} .wrap{{max-width:980px;margin:0 auto}} .card{{border:1px solid #2a3768;border-radius:14px;padding:16px;margin:14px 0;background:#121936}} .muted{{color:#a7b0d6}}
</style>
</head>
<body><div class='wrap'>
<p><a href='../../index.html'>← Back to Atlas</a> · <a href='./index.html'>Filing archive</a></p>
<div class='card'><h1>SEC filings watch</h1><p class='muted'>Generated: {stamp.isoformat()} · Watchlist filings monitor for 10-Q, 10-K, and 8-K.</p>
<p>This page is for hard-disclosure monitoring. It is most useful when you want to know whether a company actually filed something material, not just showed up in headlines.</p>
<h2>Executive summary</h2><ul>{exec_lines}</ul></div>
{''.join(cards) if cards else "<div class='card'><h2>No recent target filings found</h2><p class='muted'>Nothing in the current watchlist matched 10-Q / 10-K / 8-K in the recent 45-day window.</p></div>"}
</div></body></html>"""
    archive_path.write_text(html, encoding="utf-8")

    idx_files = sorted([p.name for p in reports_dir.glob("20*.html")], reverse=True)
    idx_items = "".join(f"<li><a href='./{escape(name)}'>{escape(name[:-5])}</a></li>" for name in idx_files)
    index_html = f"<!doctype html><html><body style='font-family:Georgia,serif;margin:24px;background:#0f1738;color:#edf2ff'><p><a href='../../index.html'>← Back to Atlas</a></p><h1>SEC filings archive</h1><p style='color:#a7b0d6'>Latest archive rebuild: {stamp.isoformat()}</p><ul>{idx_items or '<li>No reports yet.</li>'}</ul></body></html>"
    (reports_dir / "index.html").write_text(index_html, encoding="utf-8")

    (out_root / "filings-research").mkdir(parents=True, exist_ok=True)
    (out_root / "filings-research" / "summary.json").write_text(json.dumps(latest_summary, indent=2) + "\n", encoding="utf-8")
    (out_root / "filings-research" / "latest.html").write_text(html, encoding="utf-8")

    return archive_path, latest_summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watchlist", default="watchlist.json")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    archive_path, summary = build_report(load_watchlist(Path(args.watchlist)), Path(args.root))
    print(f"Wrote {archive_path}")
    print(f"Updated filings summary -> {summary['latestPath']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
