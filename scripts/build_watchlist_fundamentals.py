#!/usr/bin/env python3
"""Best-effort fundamentals refresh; never degrades existing curated fundamentals."""

from __future__ import annotations

import argparse
import json
import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

MODULES = "financialData,defaultKeyStatistics,summaryDetail,price"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_UA = "AtlasMarketIntelligence/1.0 david@example.com"
YAHOO_HEALTH_PATH = Path("data/cache/fundamentals_source_health.json")
YAHOO_COOLDOWN_HOURS = 24
YAHOO_FAIL_THRESHOLD = 3


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


def _fetch_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=25, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8"))


def _latest_from_fact(fact_block: dict[str, Any]) -> float | None:
    if not isinstance(fact_block, dict):
        return None
    units = fact_block.get("units") or {}
    candidates = []
    for unit_values in units.values():
        for row in unit_values or []:
            val = row.get("val")
            end = row.get("end") or ""
            frame = row.get("frame") or ""
            fy = row.get("fy") or 0
            fp = row.get("fp") or ""
            if val is None:
                continue
            candidates.append((str(end), str(frame), int(fy or 0), str(fp), float(val)))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][4]


def _growth_from_fact(fact_block: dict[str, Any]) -> float | None:
    if not isinstance(fact_block, dict):
        return None
    units = fact_block.get("units") or {}
    rows = []
    for unit_values in units.values():
        for row in unit_values or []:
            val = row.get("val")
            fy = row.get("fy")
            fp = row.get("fp")
            if val is None or fy is None:
                continue
            rows.append((int(fy), str(fp), float(val)))
    if len(rows) < 2:
        return None
    rows.sort(reverse=True)
    latest = rows[0][2]
    prev = None
    for fy, fp, val in rows[1:]:
        if fp == rows[0][1]:
            prev = val
            break
    if prev in (None, 0):
        return None
    return (latest - prev) / prev


def _load_yahoo_health() -> dict[str, Any]:
    if not YAHOO_HEALTH_PATH.exists():
        return {}
    try:
        return json.loads(YAHOO_HEALTH_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_yahoo_health(doc: dict[str, Any]) -> None:
    YAHOO_HEALTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    YAHOO_HEALTH_PATH.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _yahoo_in_cooldown(now: datetime, health: dict[str, Any]) -> bool:
    until = health.get("cooldown_until")
    if not until:
        return False
    try:
        return datetime.fromisoformat(until) > now
    except Exception:
        return False


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
            payload = _fetch_json(url, headers=headers)
            result = (((payload.get("quoteSummary") or {}).get("result") or [None])[0]) or {}
            if result:
                return result
        except Exception as e:
            last_error = e

    if last_error:
        raise last_error
    return {}


def _load_sec_ticker_map() -> dict[str, dict[str, Any]]:
    doc = _fetch_json(SEC_TICKERS_URL, headers={"User-Agent": SEC_UA, "Accept": "application/json"})
    out: dict[str, dict[str, Any]] = {}
    for row in doc.get("data", []) or []:
        if len(row) >= 3:
            cik, company, ticker = row[0], row[1], str(row[2]).upper()
            out[ticker] = {"cik": str(cik).zfill(10), "company": company}
    return out


def fetch_sec_companyfacts(ticker: str, sec_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    meta = sec_map.get(ticker)
    if not meta:
        raise ValueError("ticker not found in SEC map")
    url = SEC_COMPANYFACTS_URL.format(cik=meta["cik"])
    facts = _fetch_json(url, headers={"User-Agent": SEC_UA, "Accept": "application/json"})
    facts_usgaap = ((facts.get("facts") or {}).get("us-gaap") or {})
    revenue = _latest_from_fact(facts_usgaap.get("RevenueFromContractWithCustomerExcludingAssessedTax") or facts_usgaap.get("Revenues"))
    revenue_growth = _growth_from_fact(facts_usgaap.get("RevenueFromContractWithCustomerExcludingAssessedTax") or facts_usgaap.get("Revenues"))
    cash = _latest_from_fact(facts_usgaap.get("CashAndCashEquivalentsAtCarryingValue") or facts_usgaap.get("CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"))
    debt = _latest_from_fact(facts_usgaap.get("LongTermDebtAndFinanceLeaseObligations") or facts_usgaap.get("LongTermDebt") or facts_usgaap.get("DebtInstrumentCarryingAmount"))
    gross_profit = _latest_from_fact(facts_usgaap.get("GrossProfit"))
    op_cash = _latest_from_fact(facts_usgaap.get("NetCashProvidedByUsedInOperatingActivities"))
    capex = _latest_from_fact(facts_usgaap.get("PaymentsToAcquirePropertyPlantAndEquipment"))
    fcf = None
    if op_cash is not None and capex is not None:
        fcf = op_cash - abs(capex)
    gross_margin = None
    if gross_profit is not None and revenue not in (None, 0):
        gross_margin = gross_profit / revenue
    return {
        "company": facts.get("entityName") or meta["company"] or ticker,
        "market_cap_b": 0.0,
        "revenue_growth_yoy_pct": round((revenue_growth or 0.0) * 100.0, 2),
        "fcf_margin_pct": round(((fcf / revenue) * 100.0) if fcf is not None and revenue not in (None, 0) else 0.0, 2),
        "gross_margin_pct": round((gross_margin or 0.0) * 100.0, 2),
        "forward_pe": 0.0,
        "peg": 0.0,
        "net_cash_b": round((((cash or 0.0) - (debt or 0.0)) / 1_000_000_000.0), 2),
        "source_links": [url],
        "source_status": "auto-sec-companyfacts",
    }


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
    now = datetime.now(hkt)
    as_of = now.date().isoformat()

    refreshed = dict(existing_tickers)
    success = 0
    failures: list[str] = []
    sec_success = 0
    yahoo_success = 0
    yahoo_401_count = 0
    yahoo_skipped_due_to_cooldown = 0
    sec_map: dict[str, dict[str, Any]] = {}
    health = _load_yahoo_health()
    yahoo_cooldown = _yahoo_in_cooldown(now, health)
    try:
        sec_map = _load_sec_ticker_map()
    except Exception as e:
        print(f"WARN SEC map: {e}")

    for t in watchlist:
        yahoo_error = None
        if not yahoo_cooldown:
            try:
                result = fetch_quote_summary(t)
                if not result:
                    raise ValueError("empty quoteSummary result")
                refreshed[t] = build_one(t, result)
                success += 1
                yahoo_success += 1
                print(f"OK {t} yahoo")
                continue
            except HTTPError as e:
                yahoo_error = e
                print(f"WARN {t} yahoo: {e}")
                if e.code == 401:
                    yahoo_401_count += 1
                    if yahoo_401_count >= YAHOO_FAIL_THRESHOLD:
                        yahoo_cooldown = True
                        health.update({
                            "status": "cooldown",
                            "reason": "repeated-401",
                            "last_failure_at": now.replace(microsecond=0).isoformat(),
                            "cooldown_until": (now + timedelta(hours=YAHOO_COOLDOWN_HOURS)).replace(microsecond=0).isoformat(),
                            "consecutive_401": yahoo_401_count,
                        })
                        _save_yahoo_health(health)
                        print(f"INFO yahoo disabled for {YAHOO_COOLDOWN_HOURS}h after repeated 401s")
            except Exception as e:
                yahoo_error = e
                print(f"WARN {t} yahoo: {e}")
        else:
            yahoo_skipped_due_to_cooldown += 1
            print(f"INFO {t} yahoo skipped due to cooldown")

        try:
            if not sec_map:
                raise ValueError("SEC map unavailable")
            refreshed[t] = fetch_sec_companyfacts(t, sec_map)
            success += 1
            sec_success += 1
            print(f"OK {t} sec")
        except Exception as e:
            failures.append(t)
            if t in refreshed:
                refreshed[t]["source_status"] = "curated-preserved"
            print(f"WARN {t} sec: {e}")

    if yahoo_success > 0:
        health.update({
            "status": "ok",
            "reason": "healthy",
            "last_success_at": now.replace(microsecond=0).isoformat(),
            "consecutive_401": 0,
        })
        health.pop("cooldown_until", None)
        _save_yahoo_health(health)

    out: dict[str, Any] = {
        "as_of": as_of,
        "source_note": "Auto-refresh from Yahoo when available; falls back to SEC companyfacts for U.S. issuers; preserves existing curated entries on fetch failures.",
        "refresh_status": {
            "attempted": len(watchlist),
            "refreshed": success,
            "refreshed_via_yahoo": yahoo_success,
            "refreshed_via_sec": sec_success,
            "yahoo_401_count": yahoo_401_count,
            "yahoo_skipped_due_to_cooldown": yahoo_skipped_due_to_cooldown,
            "yahoo_cooldown_active": yahoo_cooldown,
            "failed": len(failures),
            "coverage_pct": round((success / len(watchlist)) * 100.0, 1) if watchlist else 0.0,
            "failed_tickers": failures,
        },
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
