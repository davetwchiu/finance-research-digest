#!/usr/bin/env python3
"""Generate ticker pages with strict contract sections and explicit provisional labeling."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

HKT = timezone(timedelta(hours=8))
UTC = timezone.utc

EXCHANGE_MAP = {
    "AAPL": "NASDAQ:AAPL",
    "AVGO": "NASDAQ:AVGO",
    "BBAI": "NYSE:BBAI",
    "BRK.B": "NYSE:BRK.B",
    "GOOG": "NASDAQ:GOOG",
    "IBM": "NYSE:IBM",
    "KTOS": "NASDAQ:KTOS",
    "LITE": "NASDAQ:LITE",
    "MSFT": "NASDAQ:MSFT",
    "NVDA": "NASDAQ:NVDA",
    "ONDS": "NASDAQ:ONDS",
    "PLTR": "NASDAQ:PLTR",
    "RDW": "NYSE:RDW",
    "RKLB": "NASDAQ:RKLB",
    "TSLA": "NASDAQ:TSLA",
    "TSM": "NYSE:TSM",
    "UUUU": "AMEX:UUUU",
}

PEERS = {
    "AAPL": ["MSFT", "GOOG", "IBM"],
    "AVGO": ["NVDA", "TSM", "LITE"],
    "BBAI": ["PLTR", "IBM", "MSFT"],
    "KTOS": ["PLTR", "RDW", "RKLB"],
    "MSFT": ["GOOG", "IBM", "AAPL"],
    "NVDA": ["AVGO", "TSM", "MSFT"],
    "ONDS": ["KTOS", "PLTR", "IBM"],
    "PLTR": ["BBAI", "IBM", "MSFT"],
    "RDW": ["RKLB", "KTOS", "PLTR"],
    "RKLB": ["RDW", "KTOS", "TSLA"],
    "TSLA": ["AAPL", "NVDA", "RKLB"],
    "TSM": ["NVDA", "AVGO", "LITE"],
    "UUUU": ["TSM", "AVGO", "IBM"],
    "GOOG": ["MSFT", "AAPL", "IBM"],
    "IBM": ["MSFT", "GOOG", "PLTR"],
    "BRK.B": ["AAPL", "MSFT", "GOOG"],
    "LITE": ["AVGO", "TSM", "NVDA"],
}

CATALYSTS = {
    "default": [
        {"name": "Mid-month US CPI / rates repricing window", "date": "2026-03-12", "impact": "Rates-sensitive multiple reset across long-duration growth."},
        {"name": "March FOMC setup window", "date": "2026-03-18", "impact": "Could alter discount-rate path, USD tone, and risk appetite."},
    ],
    "TSM": [{"name": "Mid-month semiconductor policy / tariff monitoring window", "date": "2026-03-18", "impact": "Supply-chain and capex expectations can move quickly on policy language."}],
    "NVDA": [{"name": "Mid-month semiconductor policy / tariff monitoring window", "date": "2026-03-18", "impact": "Export-control or tariff language can re-rate AI/silicon multiples fast."}],
    "AVGO": [{"name": "Mid-month semiconductor policy / tariff monitoring window", "date": "2026-03-18", "impact": "AI infra and networking multiples remain sensitive to policy and rates."}],
    "PLTR": [{"name": "US federal budget / defense contract headlines", "date": "2026-03-20", "impact": "Government-award timing can change near-term narrative and momentum."}],
    "KTOS": [{"name": "US federal budget / defense contract headlines", "date": "2026-03-20", "impact": "Defense names often move on program-funding visibility and award flow."}],
    "RDW": [{"name": "US federal budget / defense-space contract headlines", "date": "2026-03-20", "impact": "Space infrastructure names are sensitive to award cadence and sentiment."}],
    "RKLB": [{"name": "US federal budget / defense-space contract headlines", "date": "2026-03-20", "impact": "Launch cadence and government-adjacent funding headlines can move the setup."}],
}


@dataclass
class Score:
    total: int
    ta: int
    fundamentals: int


def _num(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _fmt(v: float | None, digits: int = 2, suffix: str = "") -> str:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "N/A"
    return f"{v:.{digits}f}{suffix}"


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_watchlist(path: str) -> list[str]:
    wl = (_load_json(path).get("watchlist") or [])
    return [str(x).strip().upper() for x in wl if str(x).strip()]


def _tv_symbol(ticker: str) -> str:
    return EXCHANGE_MAP.get(ticker, ticker)


def _compute_score(sig: dict, f: dict) -> Score:
    latest = sig.get("latest") or {}
    ind = sig.get("indicators") or {}
    close = _num(latest.get("close"))
    sma20 = _num(ind.get("sma20"))
    sma50 = _num(ind.get("sma50"))
    rsi = _num(ind.get("rsi14"))
    atr = _num(ind.get("atr14"))
    ta = 0
    if close and sma20:
        ta += 10 if close >= sma20 else 4
    if close and sma50:
        ta += 12 if close >= sma50 else 3
    if rsi is not None:
        ta += 12 if 48 <= rsi <= 68 else (7 if 40 <= rsi <= 75 else 3)
    if close and atr:
        atr_pct = atr / close * 100.0
        ta += 10 if atr_pct <= 3 else (7 if atr_pct <= 5 else 3)
    rev = _num(f.get("revenue_growth_yoy_pct"))
    gm = _num(f.get("gross_margin_pct"))
    pe = _num(f.get("forward_pe"))
    fcf = _num(f.get("fcf_margin_pct"))
    fundamentals = 0
    if rev is not None:
        fundamentals += 14 if rev >= 20 else (9 if rev >= 8 else 4)
    if gm is not None:
        fundamentals += 10 if gm >= 45 else (6 if gm >= 25 else 2)
    if pe is not None and pe > 0:
        fundamentals += 8 if pe <= 35 else (5 if pe <= 60 else 2)
    if fcf is not None:
        fundamentals += 8 if fcf >= 15 else (5 if fcf >= 5 else 2)
    total = max(0, min(100, ta + fundamentals + 24))
    return Score(total=total, ta=ta, fundamentals=fundamentals)


def _freshness(last_verified_hkt: str) -> tuple[str, float]:
    try:
        dt = datetime.fromisoformat(last_verified_hkt)
        age_h = (datetime.now(HKT) - dt.astimezone(HKT)).total_seconds() / 3600.0
    except Exception:
        return "unknown", 999.0
    if age_h > 24:
        return "stale", age_h
    if age_h > 12:
        return "aging", age_h
    return "fresh", age_h


def _countdown(date_str: str) -> str:
    dt = datetime.fromisoformat(date_str).replace(tzinfo=HKT)
    delta = dt.date() - datetime.now(HKT).date()
    return f"D{delta.days:+d}"


def _peer_row(ticker: str, peer: str, funds: dict[str, dict]) -> str:
    p = funds.get(peer) or {}
    return f"<li><strong>{peer}</strong>: rev growth {_fmt(_num(p.get('revenue_growth_yoy_pct')),1,'%')} · gross margin {_fmt(_num(p.get('gross_margin_pct')),1,'%')} · fwd P/E {_fmt(_num(p.get('forward_pe')),1,'x')} · market cap {_fmt(_num(p.get('market_cap_b')),1,'B')}.</li>"


def _fundamentals_refresh_note(fdoc: dict, ticker: str) -> str:
    status = (fdoc or {}).get('refresh_status') or {}
    attempted = int(status.get('attempted') or 0)
    failed = int(status.get('failed') or 0)
    if attempted <= 0 or failed <= 0:
        return ""
    refreshed = int(status.get('refreshed') or 0)
    coverage = status.get('coverage_pct')
    tickers = status.get('failed_tickers') or []
    own_failed = ticker in tickers
    scope = f"{failed}/{attempted} tickers failed Yahoo refresh"
    detail = f"refresh coverage was {coverage}%" if coverage is not None else f"only {refreshed}/{attempted} tickers refreshed"
    prefix = f"<strong>{ticker}</strong> stayed on preserved fundamentals" if own_failed else "Ticker page is using mixed fresh/preserved fundamentals"
    return f"<p class='warn'>{prefix} because {scope}; {detail}. Treat peer/fundamental comparisons as secondary until the feed recovers.</p>"


def _what_changed(news_items: list[dict]) -> tuple[str, int]:
    verified = [x for x in news_items if x.get("published_hkt") and x.get("url")]
    if len(verified) < 2:
        return "<p><strong>insufficient verified data</strong> — fewer than two dated headline facts with links were available in the last 72h from the current run.</p>", len(verified)
    lis = []
    for x in verified[:4]:
        lis.append(f"<li><strong>{x.get('published_hkt','')[:10]}</strong> — <a href='{x.get('url','')}'>{x.get('title','')}</a> <span class='muted'>[{(x.get('impact') or {}).get('sentiment','neutral')}, {(x.get('source') or 'source n/a')}]</span></li>")
    return "<ul>" + "".join(lis) + "</ul>", len(verified[:4])


def _business_reality(ticker: str, f: dict) -> tuple[str, int, bool]:
    links = f.get("source_links") or []
    as_of = f.get("as_of") or datetime.now(HKT).date().isoformat()
    facts = []
    if _num(f.get("market_cap_b")) is not None:
        facts.append(f"<li><strong>{as_of}</strong> — market cap approx {_fmt(_num(f.get('market_cap_b')),2,'B')} based on Yahoo quote data. <a href='{links[0] if links else '#'}'>source</a></li>")
    if _num(f.get("revenue_growth_yoy_pct")) is not None:
        facts.append(f"<li><strong>{as_of}</strong> — revenue growth approx {_fmt(_num(f.get('revenue_growth_yoy_pct')),2,'%')} and FCF margin {_fmt(_num(f.get('fcf_margin_pct')),2,'%')}. <a href='{links[0] if links else '#'}'>source</a></li>")
    if _num(f.get("gross_margin_pct")) is not None:
        facts.append(f"<li><strong>{as_of}</strong> — gross margin approx {_fmt(_num(f.get('gross_margin_pct')),2,'%')} and forward P/E {_fmt(_num(f.get('forward_pe')),2,'x')}. <a href='{links[1] if len(links) > 1 else (links[0] if links else '#') }'>source</a></li>")
    missing_segment_customer = True
    extra = "<p class='warn'>Segment/customer evidence is insufficiently verified in the current automated run; treat business-quality conclusions as provisional until primary IR/10-Q detail is attached.</p>"
    return ("<ul>" + "".join(facts[:3]) + "</ul>" + extra) if facts else ("<p><strong>insufficient verified data</strong> — no dated revenue/segment/customer evidence was available in the current run.</p>"), len(facts[:3]), missing_segment_customer


def _moat_compare(ticker: str, f: dict, funds: dict[str, dict], fdoc: dict) -> tuple[str, int, str]:
    peers = PEERS.get(ticker, [])[:3]
    if len(peers) < 2:
        return "<p><strong>insufficient verified data</strong> — peer set unavailable.</p>", 0, "peer set unavailable"

    own_metrics = [
        _num(f.get("revenue_growth_yoy_pct")),
        _num(f.get("gross_margin_pct")),
        _num(f.get("forward_pe")),
        _num(f.get("market_cap_b")),
    ]
    own_has_data = any(v is not None for v in own_metrics)
    own = (
        f"<p><strong>{ticker}</strong>: rev growth {_fmt(_num(f.get('revenue_growth_yoy_pct')),1,'%')} · gross margin {_fmt(_num(f.get('gross_margin_pct')),1,'%')} · fwd P/E {_fmt(_num(f.get('forward_pe')),1,'x')} · market cap {_fmt(_num(f.get('market_cap_b')),1,'B')}.</p>"
        if own_has_data
        else f"<p><strong>{ticker}</strong>: current run has no verified fundamentals feed for peer comparison, so this section stays technical-first until the feed recovers.</p>"
    )

    lis = [_peer_row(ticker, p, funds) for p in peers if funds.get(p)]
    compare_points = (1 if own_has_data else 0) + len(lis)

    refresh_note = _fundamentals_refresh_note(fdoc, ticker)

    if not own_has_data and not lis:
        return own + refresh_note + "<p class='warn'>Peer comparison deferred: the fundamentals feed did not return usable data for this ticker or its mapped peers in this run.</p>", compare_points, "fundamentals feed unavailable for peer comparison"

    if not lis:
        return own + refresh_note + "<p class='warn'>Peer comparison is limited: ticker-level fundamentals exist, but peer fundamentals were unavailable in this run.</p>", compare_points, "peer fundamentals unavailable"

    return own + refresh_note + "<ul>" + "".join(lis[:3]) + "</ul><p class='muted'>Concrete compare points used: revenue growth, gross margin, forward P/E, market cap.</p>", compare_points, ""


def _catalyst_block(ticker: str) -> tuple[str, int, bool]:
    cats = CATALYSTS.get(ticker) or CATALYSTS["default"]
    lis = []
    verified = 0
    for c in cats[:2]:
        lis.append(f"<li><strong>{c['date']}</strong> ({_countdown(c['date'])}) — {c['name']}. Expected impact path: {c['impact']}</li>")
    note = "<p class='warn'>These are macro/policy calendar anchors, not issuer-confirmed event dates. Earnings or company-specific event timing remains unverified in this run.</p>"
    return "<ul>" + "".join(lis) + "</ul>" + note, verified, True


def _plain_language_summary(ticker: str, sig: dict, score: Score) -> str:
    latest = sig.get("latest") or {}
    ind = sig.get("indicators") or {}
    close = _num(latest.get("close"))
    sma20 = _num(ind.get("sma20"))
    sma50 = _num(ind.get("sma50"))
    rsi = _num(ind.get("rsi14"))
    atr = _num(ind.get("atr14"))

    trend_bits = []
    if close is not None and sma20 is not None:
        trend_bits.append("holding above the 20-day trend" if close >= sma20 else "still below the 20-day trend")
    if close is not None and sma50 is not None:
        trend_bits.append("still above the 50-day base" if close >= sma50 else "not back above the 50-day base yet")

    momentum = "momentum is balanced"
    if rsi is not None:
        if rsi >= 60:
            momentum = "momentum is warm rather than stretched"
        elif rsi <= 40:
            momentum = "momentum is weak and needs proof of stabilization"

    risk = "volatility is manageable"
    if close and atr:
        atr_pct = atr / close * 100.0
        if atr_pct >= 8:
            risk = "volatility is high, so position sizing matters more than the headline"
        elif atr_pct >= 5:
            risk = "volatility is elevated, so expect wider swings than the benchmark"

    stance = "watchlist name, not an aggressive chase"
    if score.total >= 75:
        stance = "actionable only if price confirms the move"
    elif score.total <= 50:
        stance = "mostly a monitoring name until price and evidence improve"

    lead = trend_bits[0] if trend_bits else "setup is mixed"
    second = trend_bits[1] if len(trend_bits) > 1 else momentum
    return (
        f"<p><strong>Layman summary:</strong> {ticker} is {lead}; {second}. "
        f"Right now, {momentum}, {risk}, and this reads as a <strong>{stance}</strong>.</p>"
    )


    latest = sig.get("latest") or {}
    ind = sig.get("indicators") or {}
    close = _num(latest.get("close")) or 0.0
    sma20 = _num(ind.get("sma20")) or close
    sma50 = _num(ind.get("sma50")) or close
    atr = _num(ind.get("atr14")) or max(close * 0.03, 0.01)
    trigger = max(sma20, sma50)
    invalid = min(sma20, sma50) - 0.5 * atr
    t1 = close + 1.0 * atr
    t2 = close + 2.0 * atr
    conf = "high" if score.total >= 75 else ("medium" if score.total >= 60 else "low")
    return f"<ul><li><strong>Trigger:</strong> daily close above {_fmt(trigger,2)} with confirmation from volume / follow-through.</li><li><strong>Invalidation:</strong> two closes below {_fmt(invalid,2)} or adverse catalyst that breaks the thesis.</li><li><strong>Target 1:</strong> {_fmt(t1,2)}</li><li><strong>Target 2:</strong> {_fmt(t2,2)}</li><li><strong>Confidence:</strong> {conf}</li><li><strong>What changes my mind:</strong> weakening breadth, rising ATR without price progress, negative high-severity headlines, or deterioration in peer-relative metrics.</li></ul>"


def _setup_block(ticker: str, sig: dict, score: Score) -> str:
    latest = sig.get("latest") or {}
    ind = sig.get("indicators") or {}
    close = _num(latest.get("close")) or 0.0
    sma20 = _num(ind.get("sma20")) or close
    sma50 = _num(ind.get("sma50")) or close
    atr = _num(ind.get("atr14")) or max(close * 0.03, 0.01)
    trigger = max(sma20, sma50)
    invalid = min(sma20, sma50) - 0.5 * atr
    t1 = close + 1.0 * atr
    t2 = close + 2.0 * atr
    conf = "high" if score.total >= 75 else ("medium" if score.total >= 60 else "low")
    return f"<ul><li><strong>Trigger:</strong> daily close above {_fmt(trigger,2)} with confirmation from volume / follow-through.</li><li><strong>Invalidation:</strong> two closes below {_fmt(invalid,2)} or adverse catalyst that breaks the thesis.</li><li><strong>Target 1:</strong> {_fmt(t1,2)}</li><li><strong>Target 2:</strong> {_fmt(t2,2)}</li><li><strong>Confidence:</strong> {conf}</li><li><strong>What changes my mind:</strong> weakening breadth, rising ATR without price progress, negative high-severity headlines, or deterioration in peer-relative metrics.</li></ul>"


def _decision_view(ticker: str, sig: dict, score: Score, evidence_quality: int, freshness_state: str, provisional: bool) -> tuple[str, dict]:
    latest = sig.get("latest") or {}
    ind = sig.get("indicators") or {}
    close = _num(latest.get("close"))
    sma20 = _num(ind.get("sma20"))
    sma50 = _num(ind.get("sma50"))
    rsi = _num(ind.get("rsi14"))
    atr = _num(ind.get("atr14"))

    trend_ok = close is not None and sma20 is not None and sma50 is not None and close >= sma20 and close >= sma50
    weak_trend = close is not None and sma20 is not None and sma50 is not None and close < sma20 and close < sma50

    if freshness_state == "stale":
        action = "Do not trust the setup yet — refresh first."
        stance = "stale"
    elif provisional and evidence_quality < 55:
        action = "Monitor only — evidence is too thin for conviction."
        stance = "monitor"
    elif trend_ok and evidence_quality >= 70 and (rsi is None or rsi >= 50):
        action = "Actionable on confirmation — good candidate if price proves itself."
        stance = "actionable"
    elif weak_trend or evidence_quality < 65:
        if weak_trend and evidence_quality < 65:
            action = "Wait for proof — trend is weak and the evidence stack is still incomplete."
        elif weak_trend:
            action = "Wait for proof — price is still below trend support."
        else:
            action = "Wait for proof — the setup lacks enough verified business or catalyst evidence."
        stance = "wait"
    else:
        action = "Watch closely — setup is improving but not clean enough for size."
        stance = "watch"

    if atr and close:
        atr_pct = atr / close * 100.0
    else:
        atr_pct = None

    if atr_pct is None:
        macro_sensitivity = "medium"
    elif atr_pct >= 6:
        macro_sensitivity = "high"
    elif atr_pct >= 3:
        macro_sensitivity = "medium"
    else:
        macro_sensitivity = "lower"

    why_now = []
    gap20 = ((close - sma20) / sma20 * 100.0) if close is not None and sma20 not in (None, 0) else None
    gap50 = ((close - sma50) / sma50 * 100.0) if close is not None and sma50 not in (None, 0) else None
    if trend_ok and gap20 is not None and gap50 is not None:
        why_now.append(f"price is above trend support (+{gap20:.1f}% vs 20-day, +{gap50:.1f}% vs 50-day)")
    elif weak_trend and gap20 is not None and gap50 is not None:
        why_now.append(f"price is still below trend support ({gap20:.1f}% vs 20-day, {gap50:.1f}% vs 50-day)")
    else:
        why_now.append("price is mixed across the key trend lines")

    if rsi is not None:
        if rsi >= 60:
            why_now.append(f"RSI {rsi:.1f} keeps momentum constructive without looking fully blown out")
        elif rsi <= 40:
            why_now.append(f"RSI {rsi:.1f} still points to weak momentum that needs stabilization")
        else:
            why_now.append(f"RSI {rsi:.1f} is neutral, so the next move still needs confirmation")

    if atr is not None and close not in (None, 0):
        atr_pct = atr / close * 100.0
        why_now.append(f"ATR is running at {atr_pct:.1f}% of price, so swing risk is {'high' if atr_pct >= 8 else 'elevated' if atr_pct >= 5 else 'contained'}")

    if provisional:
        why_now.append(f"the page is still provisional because one or more verification gates remain open (surface score {evidence_quality}/100)")
    else:
        why_now.append(f"the verification stack is strong enough to lean more on the setup ({evidence_quality}/100)")

    html = (
        "<div class='decision-shell'>"
        f"<div class='decision-hero {stance}'><div class='decision-kicker'>Decision view</div><div class='decision-action'>{action}</div>"
        f"<div class='decision-sub'>Why now: {'; '.join(why_now)}.</div></div>"
        "<div class='decision-grid'>"
        f"<div class='decision-metric'><span class='meta-label'>Action stance</span><span class='meta-value'>{stance.upper()}</span></div>"
        f"<div class='decision-metric'><span class='meta-label'>Macro sensitivity</span><span class='meta-value'>{macro_sensitivity.upper()}</span></div>"
        f"<div class='decision-metric'><span class='meta-label'>Technical score</span><span class='meta-value'>{score.ta}/44</span></div>"
        f"<div class='decision-metric'><span class='meta-label'>Fundamental score</span><span class='meta-value'>{score.fundamentals}/40</span></div>"
        "</div></div>"
    )
    return html, {"stance": stance, "macroSensitivity": macro_sensitivity, "actionText": action}


def build_page(ticker: str, sig: dict, f: dict, funds: dict[str, dict], fdoc: dict, news: dict, report_path: str, last_verified_hkt: str) -> tuple[str, dict]:
    score = _compute_score(sig, f)
    freshness_state, age_h = _freshness(last_verified_hkt)
    items = news.get("items") or []
    changed_html, changed_evidence = _what_changed(items)
    biz_html, biz_evidence, biz_missing = _business_reality(ticker, f)
    moat_html, moat_points, moat_reason = _moat_compare(ticker, f, funds, fdoc)
    catalyst_html, catalyst_verified, catalyst_unverified = _catalyst_block(ticker)
    setup_html = _setup_block(ticker, sig, score)
    plain_language_html = _plain_language_summary(ticker, sig, score)
    reasons = []
    if changed_evidence < 2:
        reasons.append("evidence below threshold: last 72h changes")
    if biz_missing:
        reasons.append("business reality missing segment/customer proof")
    if moat_points < 3:
        reasons.append(moat_reason or "peer comparison limited")
    if catalyst_unverified:
        reasons.append("catalyst calendar unverified")
    if freshness_state == "stale":
        reasons.append("stale data not suitable for confident publish")
    evidence_quality = max(5, min(100, changed_evidence * 15 + biz_evidence * 12 + moat_points * 8 + score.total // 2 - (15 if catalyst_unverified else 0) - (20 if freshness_state == 'stale' else 0)))
    provisional = len(reasons) > 0
    status = "PROVISIONAL" if provisional else "VERIFIED"
    decision_html, decision_meta = _decision_view(ticker, sig, score, evidence_quality, freshness_state, provisional)
    stale_banner = "<div class='banner stale'>Stale warning: last verified evidence is older than 24h. Treat this page as stale until refreshed.</div>" if freshness_state == "stale" else ""
    prov_banner = f"<div class='banner provisional'>Quality gate state: {status}. Reasons: {'; '.join(reasons) if reasons else 'none'}.</div>" if provisional else "<div class='banner ok'>Quality gate state: VERIFIED.</div>"
    html = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{ticker}</title><link rel='icon' type='image/png' href='../assets/favicon.png'><style>body{{font-family:Georgia,'Iowan Old Style','Palatino Linotype',serif;margin:24px;background:radial-gradient(1000px 480px at 18% -10%, #243a78 0%, #0c1330 46%);color:#edf2ff;line-height:1.68}}a{{color:#9bb8ff;word-break:break-all}}.card{{border:1px solid #2a3768;border-radius:14px;padding:16px;margin:12px 0;background:rgba(18,25,54,.92);box-shadow:0 12px 28px rgba(0,0,0,.16)}}.muted{{color:#a7b0d6}}.banner{{padding:10px 12px;border-radius:10px;margin:12px 0;font-weight:600}}.provisional{{background:#4b1f27;border:1px solid #a65264}}.stale{{background:#4a3a14;border:1px solid #af8a2a}}.ok{{background:#153c28;border:1px solid #2f8f5a}}.pill{{display:inline-block;border:1px solid #3a4c88;border-radius:999px;padding:3px 10px;font-size:12px;color:#dfe7ff;margin-right:6px;margin-bottom:6px}}.meta-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 14px;margin-top:12px}}.meta-item{{border:1px solid #2a3768;border-radius:10px;padding:10px 12px;background:#0f1733}}.meta-label{{display:block;font-size:12px;color:#a7b0d6;margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em;font-family:-apple-system,Segoe UI,Roboto,sans-serif}}.meta-value{{font-weight:600;color:#eef3ff;font-family:-apple-system,Segoe UI,Roboto,sans-serif}}.decision-shell{{display:grid;gap:12px}}.decision-hero{{border-radius:14px;padding:16px;border:1px solid #3b4d8f;background:linear-gradient(180deg,#16214b,#0f1733)}}.decision-hero.actionable{{border-color:#2f8f5a;background:linear-gradient(180deg,#173726,#10261a)}}.decision-hero.watch{{border-color:#7b6630;background:linear-gradient(180deg,#332814,#21190f)}}.decision-hero.wait,.decision-hero.monitor,.decision-hero.stale{{border-color:#8a4b4b;background:linear-gradient(180deg,#351a1f,#241116)}}.decision-kicker{{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#a7b0d6;font-family:-apple-system,Segoe UI,Roboto,sans-serif}}.decision-action{{font-size:24px;font-weight:700;line-height:1.2;margin-top:6px}}.decision-sub{{margin-top:8px;color:#d6defe}}.decision-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}}.decision-metric{{border:1px solid #2a3768;border-radius:10px;padding:10px 12px;background:#0f1733}}details.card summary{{cursor:pointer;font-weight:700;font-family:-apple-system,Segoe UI,Roboto,sans-serif}}.warn{{color:#ffd27d}}h1{{font-size:34px;letter-spacing:.2px;margin-bottom:8px}}h2{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;letter-spacing:.2px}}@media (max-width:860px){{.meta-grid,.decision-grid{{grid-template-columns:1fr 1fr}}}}@media (max-width:560px){{.meta-grid,.decision-grid{{grid-template-columns:1fr}}body{{margin:16px}}}}</style></head><body>
<p><a href='../index.html'>← Back</a> · <a href='../{report_path}'>Daily report</a></p>
<h1>{ticker} — Atlas research brief</h1>
<div class='card'><h2>Verification status</h2><div class='meta-grid'><div class='meta-item'><span class='meta-label'>Last verified</span><span class='meta-value'>{last_verified_hkt} HKT</span></div><div class='meta-item'><span class='meta-label'>Freshness state</span><span class='meta-value'>{freshness_state}</span></div><div class='meta-item'><span class='meta-label'>Evidence quality score</span><span class='meta-value'>{evidence_quality}/100</span></div><div class='meta-item'><span class='meta-label'>TradingView mapping</span><span class='meta-value'>{_tv_symbol(ticker)}</span></div></div></div>
{decision_html}
{stale_banner}{prov_banner}
<div class='card'><h2>At a glance</h2><p><span class='pill'>Status: {status}</span><span class='pill'>Score: {score.total}/100</span><span class='pill'>TA: {score.ta}</span><span class='pill'>Fundamentals: {score.fundamentals}</span><span class='pill'>Freshness age: {_fmt(age_h,1,'h')}</span></p>{plain_language_html}<p class='muted'>Hard rule: no evidence, no claim. Thin evidence stays clearly labeled instead of being dressed up as conviction.</p></div>
<details class='card'><summary>Technical evidence, catalysts, and verification notes</summary>
<div class='card'><h2>1. What changed in last 72h</h2>{changed_html}</div>
<div class='card'><h2>2. Business reality</h2>{biz_html}</div>
<div class='card'><h2>3. Moat + competitor check</h2>{moat_html}</div>
<div class='card'><h2>4. Catalyst calendar next 30d</h2>{catalyst_html}</div>
<div class='card'><h2>5. Risk map</h2><ol><li><strong>Rates / valuation compression:</strong> long-duration equities re-rate lower if yields back up again. <em>Invalidation signal:</em> rates cool while price holds above trend.</li><li><strong>Company-specific execution miss:</strong> contract, delivery, demand, or guide slippage can break the setup. <em>Invalidation signal:</em> management or order-flow evidence stabilizes instead of worsening.</li><li><strong>Negative high-severity headline cluster:</strong> lawsuit, downgrade, export-control, tariff, or funding shock. <em>Invalidation signal:</em> market absorbs the headline and price/volume remain constructive.</li></ol></div>
<div class='card'><h2>6. Actionable setup</h2>{setup_html}</div>
</details>
<div class='card'><h2>Visual context</h2><iframe title='TradingView chart for {ticker}' src='https://s.tradingview.com/widgetembed/?symbol={_tv_symbol(ticker)}&interval=D&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=f1f3f6&theme=dark&style=1&timezone=Asia%2FHong_Kong' width='100%' height='420' frameborder='0' allowtransparency='true' scrolling='no'></iframe></div>
</body></html>"""
    meta = {
        "ticker": ticker,
        "lastVerifiedHKT": last_verified_hkt,
        "freshnessState": freshness_state,
        "evidenceQualityScore": evidence_quality,
        "provisional": provisional,
        "reasons": reasons,
        "whatChangedEvidenceCount": changed_evidence,
        "businessEvidenceCount": biz_evidence,
        "moatComparePoints": moat_points,
        "catalystVerifiedCount": catalyst_verified,
        "score": score.total,
        "decision": decision_meta,
    }
    return html, meta


def _latest_report_path(reports_dir: str) -> str:
    cands = sorted([p.name for p in Path(reports_dir).glob('20*.html')])
    return f"reports/{cands[-1]}" if cands else "reports/index.html"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--signals', default='data/cache/signals_local.json')
    ap.add_argument('--fundamentals', default='data/pilot_fundamentals.json')
    ap.add_argument('--watchlist', default='watchlist.json')
    ap.add_argument('--news', default='data/cache/ticker_news_digest.json')
    ap.add_argument('--report', default='')
    ap.add_argument('--reports-dir', default='reports')
    ap.add_argument('--tickers-dir', default='tickers')
    ap.add_argument('--meta', default='data/cache/ticker_generation_meta.json')
    args = ap.parse_args()

    signals_doc = _load_json(args.signals)
    fdoc = _load_json(args.fundamentals)
    news_doc = _load_json(args.news) if Path(args.news).exists() else {"tickers": {}}
    watchlist = _load_watchlist(args.watchlist)
    funds = (fdoc.get('tickers') or {}) if isinstance(fdoc, dict) else {}
    news_map = (news_doc.get('tickers') or {}) if isinstance(news_doc, dict) else {}
    report_path = args.report.strip() or _latest_report_path(args.reports_dir)
    last_verified_hkt = (news_doc.get('generated_at') or datetime.now(HKT).replace(microsecond=0).isoformat())

    out_dir = Path(args.tickers_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_meta = {}
    for ticker in watchlist:
        sig = ((signals_doc.get('signals') or {}).get(ticker) or {})
        if not sig:
            raise ValueError(f'missing signal for {ticker}')
        f = funds.get(ticker) or {}
        n = news_map.get(ticker) or {}
        html, meta = build_page(ticker, sig, f, funds, fdoc, n, report_path, last_verified_hkt)
        (out_dir / f'{ticker}.html').write_text(html, encoding='utf-8')
        pages_meta[ticker] = meta
        print(f"wrote {ticker} provisional={meta['provisional']} score={meta['evidenceQualityScore']}")

    meta = {
        'generated_at_utc': datetime.now(UTC).replace(microsecond=0).isoformat(),
        'generated_at_hkt': datetime.now(HKT).replace(microsecond=0).isoformat(),
        'report': report_path,
        'pages': pages_meta,
    }
    Path(args.meta).parent.mkdir(parents=True, exist_ok=True)
    Path(args.meta).write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {args.meta}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
