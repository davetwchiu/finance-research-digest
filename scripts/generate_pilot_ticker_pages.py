#!/usr/bin/env python3
"""Generate deep pilot ticker pages (NVDA/PLTR/TSLA) with deterministic TA+fundamental verdicts."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

PILOTS = ("NVDA", "PLTR", "TSLA")


@dataclass
class Score:
    ta: int
    fundamentals: int

    @property
    def total(self) -> int:
        return max(0, min(100, self.ta + self.fundamentals))


def _num(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _fmt(v: float | None, digits: int = 2) -> str:
    if v is None:
        return "N/A"
    return f"{v:.{digits}f}"


def _compute_scores(sig: Dict[str, Any], f: Dict[str, Any]) -> Tuple[Score, Dict[str, Any]]:
    close = _num((sig.get("latest") or {}).get("close"))
    ind = sig.get("indicators") or {}
    sma20 = _num(ind.get("sma20"))
    sma50 = _num(ind.get("sma50"))
    rsi = _num(ind.get("rsi14"))
    atr = _num(ind.get("atr14"))

    ta = 0
    if close and sma20:
        ta += 12 if close >= sma20 else 4
    if close and sma50:
        ta += 14 if close >= sma50 else 3
    if rsi is not None:
        if 50 <= rsi <= 68:
            ta += 14
        elif 40 <= rsi < 50 or 68 < rsi <= 75:
            ta += 8
        else:
            ta += 3
    if close and atr:
        atr_pct = atr / close * 100.0
        if atr_pct <= 3.0:
            ta += 10
        elif atr_pct <= 5.0:
            ta += 7
        else:
            ta += 3
    else:
        atr_pct = None

    rev = _num(f.get("revenue_growth_yoy_pct")) or 0.0
    fcf = _num(f.get("fcf_margin_pct")) or 0.0
    gross = _num(f.get("gross_margin_pct")) or 0.0
    pe = _num(f.get("forward_pe")) or 0.0
    peg = _num(f.get("peg")) or 99.0
    net_cash = _num(f.get("net_cash_b")) or 0.0

    fundamentals = 0
    fundamentals += 18 if rev >= 30 else (12 if rev >= 15 else 6)
    fundamentals += 12 if fcf >= 20 else (8 if fcf >= 10 else 4)
    fundamentals += 10 if gross >= 45 else (6 if gross >= 25 else 2)
    fundamentals += 10 if pe <= 45 else (6 if pe <= 70 else 2)
    fundamentals += 8 if peg <= 1.5 else (5 if peg <= 2.5 else 2)
    fundamentals += 6 if net_cash >= 5 else (4 if net_cash >= 1 else 1)

    return Score(ta=ta, fundamentals=fundamentals), {
        "close": close,
        "sma20": sma20,
        "sma50": sma50,
        "rsi14": rsi,
        "atr14": atr,
        "atr_pct": atr_pct,
        "rev_growth": rev,
        "fcf_margin": fcf,
        "gross_margin": gross,
        "forward_pe": pe,
        "peg": peg,
        "net_cash_b": net_cash,
    }


def _verdict(total: int) -> str:
    if total >= 80:
        return "GREEN — High-conviction long bias"
    if total >= 65:
        return "YELLOW+ — Constructive but needs trigger discipline"
    if total >= 50:
        return "YELLOW — Mixed setup, tactical only"
    return "RED — Avoid fresh long risk"


def _trigger_block(m: Dict[str, Any]) -> Tuple[str, str, str]:
    close = m["close"] or 0.0
    sma20 = m["sma20"] or close
    sma50 = m["sma50"] or close
    trigger = max(sma20, sma50)
    invalidation = min(sma20, sma50) * 0.985
    t1 = close * 1.08
    return (f"Daily close > {_fmt(trigger)} with volume expansion vs 20D average.",
            f"Two consecutive closes < {_fmt(invalidation)}.",
            f"Target ladder: {_fmt(t1)} (+8%) then trail toward +15% if breadth stays risk-on.")


def build_page(ticker: str, sig: Dict[str, Any], f: Dict[str, Any], report_path: str, generated_at_utc: str, generated_at_hkt: str) -> str:
    score, m = _compute_scores(sig, f)
    verdict = _verdict(score.total)
    trigger, invalidation, targets = _trigger_block(m)

    evidence = [
        f"TA score {score.ta}/50 from trend (close vs SMA20/SMA50), momentum (RSI14), and realized volatility (ATR%).",
        f"Fundamentals score {score.fundamentals}/50 from growth, cash generation, margins, valuation, and balance-sheet buffer.",
        f"Deterministic total score {score.total}/100 → verdict bucket: {verdict}.",
        "All thresholds are static and reproducible; no LLM-based scoring is used.",
    ]

    links = " · ".join([f"<a href='{u}'>{u}</a>" for u in f.get("source_links", [])])

    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{ticker}</title><link rel='icon' type='image/png' href='../assets/favicon.png'><style>body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;background:#0c1330;color:#e8ecff;line-height:1.58}}a{{color:#9bb8ff;word-break:break-all}}.card{{border:1px solid #2a3768;border-radius:12px;padding:14px;margin:12px 0;background:#121936}}.muted{{color:#a7b0d6}}table{{width:100%;border-collapse:collapse}}th,td{{border-bottom:1px solid #2a3768;padding:8px;text-align:left}}</style></head><body>
<p><a href='../index.html'>← Back</a> · <a href='../{report_path}'>Daily report</a></p>
<h1>{ticker} — Deep Pilot v3</h1>
<p class='muted'>Last generated (UTC): {generated_at_utc} · Last generated (HKT): {generated_at_hkt} · Fundamentals as-of: {f.get('as_of','N/A')}</p>
<div class='card'><h2>Layman summary (read this first)</h2><p><strong>{verdict}</strong></p><p>Simple read: score is <strong>{score.total}/100</strong>. This setup is rule-based, so the same inputs produce the same verdict every time.</p><ul><li><strong>If bullish continuation appears:</strong> {trigger}</li><li><strong>If setup fails:</strong> {invalidation}</li><li><strong>Upside roadmap:</strong> {targets}</li></ul></div>
<div class='card'><h2>Deterministic verdict</h2><p><strong>{verdict}</strong></p><p>Total score: <strong>{score.total}/100</strong> (TA {score.ta}/50 + Fundamentals {score.fundamentals}/50).</p><ul>{''.join([f'<li>{e}</li>' for e in evidence])}</ul></div>
<details class='card'><summary><strong>Technical evidence (expand)</strong></summary>
<div><h2>Technical block (real inputs)</h2><table><tr><th>Metric</th><th>Value</th><th>Interpretation</th></tr>
<tr><td>Close</td><td>{_fmt(m['close'],4)}</td><td>Reference close used in all trigger math.</td></tr>
<tr><td>SMA20</td><td>{_fmt(m['sma20'],4)}</td><td>Short trend control line.</td></tr>
<tr><td>SMA50</td><td>{_fmt(m['sma50'],4)}</td><td>Intermediate trend control line.</td></tr>
<tr><td>RSI14</td><td>{_fmt(m['rsi14'],2)}</td><td>Momentum state; 50-68 preferred for continuation quality.</td></tr>
<tr><td>ATR14</td><td>{_fmt(m['atr14'],4)}</td><td>Absolute volatility estimate.</td></tr>
<tr><td>ATR % of close</td><td>{_fmt(m['atr_pct'],2)}%</td><td>Risk normalization for position sizing.</td></tr></table></div>
<div><h2>Fundamentals block (real inputs)</h2><table><tr><th>Metric</th><th>Value</th><th>Role in score</th></tr>
<tr><td>Revenue growth YoY</td><td>{_fmt(m['rev_growth'],1)}%</td><td>Growth durability bucket.</td></tr>
<tr><td>FCF margin</td><td>{_fmt(m['fcf_margin'],1)}%</td><td>Cash conversion quality.</td></tr>
<tr><td>Gross margin</td><td>{_fmt(m['gross_margin'],1)}%</td><td>Pricing power/moat proxy.</td></tr>
<tr><td>Forward P/E</td><td>{_fmt(m['forward_pe'],1)}x</td><td>Valuation pressure indicator.</td></tr>
<tr><td>PEG</td><td>{_fmt(m['peg'],2)}x</td><td>Growth-adjusted valuation guardrail.</td></tr>
<tr><td>Net cash</td><td>{_fmt(m['net_cash_b'],1)}B</td><td>Balance-sheet shock absorber.</td></tr></table>
<p class='muted'>Primary references: {links}</p></div></details>
<div class='card'><h2>Risk map</h2><ol>
<li>Macro rate shock: if 10Y yields reprice +25bp quickly, high-duration multiple names compress first.</li>
<li>Earnings guide miss: score must be recomputed immediately if forward growth assumptions break.</li>
<li>Policy/geopolitical headline: semis and defence-adjacent names can gap outside ATR assumptions.</li>
</ol></div>
<div class='card'><h2>Quality gate evidence</h2><ul>
<li>Depth checklist: TA table + Fundamentals table + deterministic thresholds + risk map = COMPLETE.</li>
<li>Timestamped artifact: this page records UTC/HKT generation timestamps.</li>
<li>Publish policy: this page must pass scripts/qc_ticker_depth.py before deploy.</li>
</ul></div>
</body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate deep pilot ticker pages")
    ap.add_argument("--signals", default="data/cache/signals_local.json")
    ap.add_argument("--fundamentals", default="data/pilot_fundamentals.json")
    ap.add_argument("--report", default="reports/2026-03-03.html")
    ap.add_argument("--tickers-dir", default="tickers")
    ap.add_argument("--meta", default="data/cache/ticker_generation_meta.json")
    args = ap.parse_args()

    signals_doc = json.loads(Path(args.signals).read_text(encoding="utf-8"))
    fdoc = json.loads(Path(args.fundamentals).read_text(encoding="utf-8"))

    now_utc = datetime.now(timezone.utc)
    now_hkt = now_utc.astimezone(timezone.utc).astimezone()
    # deterministic explicit HKT conversion without external deps
    from datetime import timedelta
    hkt = timezone(timedelta(hours=8))
    now_hkt = now_utc.astimezone(hkt)

    generated_at_utc = now_utc.isoformat()
    generated_at_hkt = now_hkt.isoformat()

    out_dir = Path(args.tickers_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for t in PILOTS:
        sig = (signals_doc.get("signals") or {}).get(t)
        f = (fdoc.get("tickers") or {}).get(t)
        if not sig or not isinstance(sig, dict) or not sig.get("ok"):
            raise ValueError(f"Missing valid TA signal for pilot {t}")
        if not f or not isinstance(f, dict):
            raise ValueError(f"Missing fundamentals for pilot {t}")
        f = dict(f)
        f["as_of"] = fdoc.get("as_of")
        html = build_page(t, sig, f, args.report, generated_at_utc, generated_at_hkt)
        path = out_dir / f"{t}.html"
        path.write_text(html, encoding="utf-8")
        written.append(str(path))

    meta = {
        "generated_at_utc": generated_at_utc,
        "generated_at_hkt": generated_at_hkt,
        "tickers": list(PILOTS),
        "report": args.report,
        "generator": "scripts/generate_pilot_ticker_pages.py",
    }
    Path(args.meta).parent.mkdir(parents=True, exist_ok=True)
    Path(args.meta).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print("Wrote pilots:", ", ".join(written))
    print(f"Wrote {args.meta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
