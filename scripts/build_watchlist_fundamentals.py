#!/usr/bin/env python3
"""Best-effort fundamentals refresh; never degrades existing curated fundamentals."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

MODULES = "financialData,defaultKeyStatistics,summaryDetail,price"


def _val(x: Any) -> float | None:
    if isinstance(x, dict):
        if "raw" in x and x["raw"] is not None:
            return float(x["raw"])
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def _load_watchlist(path: str) -> list[str]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    wl = doc.get("watchlist") if isinstance(doc, dict) else None
    if not isinstance(wl, list) or not wl:
        raise ValueError(f"Invalid or empty watchlist in {path}")
    return [str(x).strip().upper() for x in wl if str(x).strip()]


def _to_yahoo_symbol(ticker: str) -> str:
    return ticker.replace(".", "-")


def fetch_quote_summary(ticker: str) -> dict[str, Any]:
    symbol = _to_yahoo_symbol(ticker)
    hosts = ["query2.finance.yahoo.com", "query1.finance.yahoo.com"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://finance.yahoo.com/",
        "Origin": "https://finance.yahoo.com",
    }

    last_error: Exception | None = None
    for host in hosts:
        url = f"https://{host}/v10/finance/quoteSummary/{quote(symbol)}?modules={MODULES}"
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=20) as r:
                payload = json.loads(r.read().decode("utf-8"))
            result = (((payload.get("quoteSummary") or {}).get("result") or [None])[0]) or {}
            if result:
                return result
        except Exception as e:
            last_error = e

    if last_error:
        raise last_error
    return {}


def build_one(ticker: str, result: dict[str, Any]) -> dict[str, Any]:
    fd = result.get("financialData") or {}
    ks = result.get("defaultKeyStatistics") or {}
    sd = result.get("summaryDetail") or {}
    pr = result.get("price") or {}

    total_revenue = _val(fd.get("totalRevenue"))
    free_cash_flow = _val(fd.get("freeCashflow"))
    gross_margins = _val(fd.get("grossMargins"))
    revenue_growth = _val(fd.get("revenueGrowth"))

    total_cash = _val(fd.get("totalCash"))
    total_debt = _val(fd.get("totalDebt"))

    forward_pe = _val(ks.get("forwardPE"))
    if forward_pe is None:
        forward_pe = _val(sd.get("forwardPE"))

    peg = _val(ks.get("pegRatio"))

    market_cap = _val(pr.get("marketCap"))

    fcf_margin_pct = None
    if total_revenue and free_cash_flow is not None and total_revenue != 0:
        fcf_margin_pct = (free_cash_flow / total_revenue) * 100.0

    net_cash_b = None
    if total_cash is not None and total_debt is not None:
        net_cash_b = (total_cash - total_debt) / 1_000_000_000.0

    return {
        "company": (pr.get("longName") or ticker),
        "market_cap_b": round((market_cap or 0.0) / 1_000_000_000.0, 2),
        "revenue_growth_yoy_pct": round((revenue_growth or 0.0) * 100.0, 2),
        "fcf_margin_pct": round(fcf_margin_pct or 0.0, 2),
        "gross_margin_pct": round((gross_margins or 0.0) * 100.0, 2),
        "forward_pe": round(forward_pe or 0.0, 2),
        "peg": round((peg if peg is not None else 2.0), 2),
        "net_cash_b": round(net_cash_b or 0.0, 2),
        "source_links": [
            f"https://finance.yahoo.com/quote/{_to_yahoo_symbol(ticker)}/financials",
            f"https://finance.yahoo.com/quote/{_to_yahoo_symbol(ticker)}/key-statistics",
        ],
        "source_status": "auto-yahoo",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watchlist", default="watchlist.json")
    ap.add_argument("--output", default="data/pilot_fundamentals.json")
    args = ap.parse_args()

    watchlist = _load_watchlist(args.watchlist)
    out_path = Path(args.output)

    existing: dict[str, Any] = {}
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    existing_tickers = dict((existing.get("tickers") or {}))

    hkt = timezone(timedelta(hours=8))
    as_of = datetime.now(hkt).date().isoformat()

    refreshed = dict(existing_tickers)
    success = 0
    failures: list[str] = []

    for t in watchlist:
        try:
            result = fetch_quote_summary(t)
            if not result:
                raise ValueError("empty quoteSummary result")
            refreshed[t] = build_one(t, result)
            success += 1
            print(f"OK {t}")
        except Exception as e:
            failures.append(t)
            if t in refreshed:
                refreshed[t]["source_status"] = "curated-preserved"
            print(f"WARN {t}: {e}")

    out: dict[str, Any] = {
        "as_of": as_of,
        "source_note": "Auto-refresh from Yahoo when available; preserves existing curated entries on fetch failures.",
        "tickers": refreshed,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} (auto-refreshed {success}/{len(watchlist)}; total entries {len(refreshed)})")
    if failures:
        print("Failed refresh:", ", ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
