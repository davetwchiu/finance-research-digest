#!/usr/bin/env python3
"""Build deeper local-first Atlas analysis from signals_local.json.

Deterministic only (no LLM). Produces:
- Market regime composite (breadth + momentum + volatility)
- Theme buckets with relative-strength proxy from SMA gaps
- Signal quality diagnostics (missing/stale)
- Ranked watchlist triage
- Plain-language conclusions (5-8 bullets)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


THEME_MAP = {
    "AI mega-cap": {"AAPL", "MSFT", "NVDA", "GOOG", "AVGO", "TSM", "TSLA"},
    "defence/space": {"KTOS", "RDW", "RKLB", "ONDS", "PLTR", "LITE"},
    "energy/materials": {"UUUU"},
    "diversified": {"BRK.B", "IBM", "BBAI"},
}


def _num(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _round(v: Optional[float], d: int = 2) -> Optional[float]:
    if v is None:
        return None
    return round(v, d)


def _ticker_theme(ticker: str) -> str:
    for theme, names in THEME_MAP.items():
        if ticker in names:
            return theme
    return "diversified"


def _score_ticker(close: Optional[float], sma20: Optional[float], sma50: Optional[float], rsi14: Optional[float], atr14: Optional[float]) -> Dict[str, Any]:
    # Base quality + directional score for deterministic triage.
    score = 0.0
    flags: List[str] = []

    if close is None or close <= 0:
        return {"score": -999.0, "flags": ["no_price"]}

    if sma20 is not None and close >= sma20:
        score += 1.2
        flags.append("above_sma20")
    elif sma20 is not None:
        score -= 1.0

    if sma50 is not None and close >= sma50:
        score += 1.4
        flags.append("above_sma50")
    elif sma50 is not None:
        score -= 1.1

    if rsi14 is not None:
        if 55 <= rsi14 <= 70:
            score += 1.2
            flags.append("healthy_momentum")
        elif 40 <= rsi14 < 55:
            score += 0.4
        elif rsi14 > 75:
            score -= 0.5
            flags.append("overheated")
        elif rsi14 < 35:
            score -= 0.8
            flags.append("weak_momentum")

    if atr14 is not None:
        atr_pct = (atr14 / close) * 100.0
        if atr_pct >= 5.0:
            score -= 0.9
            flags.append("high_volatility")
        elif atr_pct <= 2.5:
            score += 0.4

    return {"score": round(score, 3), "flags": flags}


def build(signals_doc: Dict[str, Any]) -> Dict[str, Any]:
    signals = signals_doc.get("signals", {}) if isinstance(signals_doc, dict) else {}
    total = len(signals)

    valid = 0
    above20 = 0
    above50 = 0
    rsi_vals: List[float] = []
    atr_pcts: List[float] = []

    # quality diagnostics
    required_fields = ["close", "sma20", "sma50", "rsi14", "atr14"]
    missing_fields = 0
    field_slots = max(total, 1) * len(required_fields)
    stale_count = 0

    themes: Dict[str, Dict[str, Any]] = {
        k: {"count": 0, "members": [], "avg_sma20_gap_pct": None, "avg_sma50_gap_pct": None}
        for k in THEME_MAP
    }

    triage_rows: List[Dict[str, Any]] = []

    for ticker, row in signals.items():
        if not isinstance(row, dict) or not row.get("ok"):
            missing_fields += len(required_fields)
            stale_count += 1
            triage_rows.append({"ticker": ticker, "priority": "low_priority", "score": -999.0, "reasons": ["data_unavailable"]})
            continue

        latest = row.get("latest", {}) or {}
        ind = row.get("indicators", {}) or {}
        close = _num(latest.get("close"))
        sma20 = _num(ind.get("sma20"))
        sma50 = _num(ind.get("sma50"))
        rsi14 = _num(ind.get("rsi14"))
        atr14 = _num(ind.get("atr14"))
        samples = int(row.get("samples") or 0)

        fields = {"close": close, "sma20": sma20, "sma50": sma50, "rsi14": rsi14, "atr14": atr14}
        missing_fields += sum(1 for f in required_fields if fields[f] is None)

        if samples < 90 or (sma20 is None and sma50 is None):
            stale_count += 1

        if close is not None and close > 0:
            valid += 1
            if sma20 is not None and close >= sma20:
                above20 += 1
            if sma50 is not None and close >= sma50:
                above50 += 1
            if rsi14 is not None:
                rsi_vals.append(rsi14)
            if atr14 is not None:
                atr_pcts.append((atr14 / close) * 100.0)

        theme = _ticker_theme(ticker)
        bucket = themes[theme]
        bucket["count"] += 1

        gap20 = ((close - sma20) / sma20 * 100.0) if (close is not None and sma20 not in (None, 0)) else None
        gap50 = ((close - sma50) / sma50 * 100.0) if (close is not None and sma50 not in (None, 0)) else None
        bucket["members"].append({
            "ticker": ticker,
            "gap_sma20_pct": _round(gap20, 2),
            "gap_sma50_pct": _round(gap50, 2),
        })

        scored = _score_ticker(close, sma20, sma50, rsi14, atr14)
        score = scored["score"]
        reasons = scored["flags"]

        if score >= 2.0:
            priority = "high_attention"
        elif score >= 0.3:
            priority = "watch"
        else:
            priority = "low_priority"

        triage_rows.append({"ticker": ticker, "priority": priority, "score": score, "reasons": reasons})

    # Theme relative strength proxies
    for theme, bucket in themes.items():
        g20 = [x["gap_sma20_pct"] for x in bucket["members"] if x["gap_sma20_pct"] is not None]
        g50 = [x["gap_sma50_pct"] for x in bucket["members"] if x["gap_sma50_pct"] is not None]
        bucket["avg_sma20_gap_pct"] = _round(sum(g20) / len(g20), 2) if g20 else None
        bucket["avg_sma50_gap_pct"] = _round(sum(g50) / len(g50), 2) if g50 else None

    valid_universe = max(valid, 1)
    breadth_score = ((above20 / valid_universe) * 100.0 - 50.0) * 1.6

    avg_rsi = sum(rsi_vals) / len(rsi_vals) if rsi_vals else 50.0
    momentum_score = (avg_rsi - 50.0) * 1.5

    avg_atr_pct = sum(atr_pcts) / len(atr_pcts) if atr_pcts else 3.0
    # Lower vol => better. Neutral around 3.2%
    volatility_score = (3.2 - avg_atr_pct) * 10.0

    composite = _clip(breadth_score + momentum_score + volatility_score, -100.0, 100.0)
    if composite >= 20:
        regime = "risk_on"
    elif composite <= -20:
        regime = "risk_off"
    else:
        regime = "neutral"

    triage_sorted = sorted(triage_rows, key=lambda x: (x["priority"] != "high_attention", x["priority"] != "watch", -x["score"], x["ticker"]))

    high_attention = [x for x in triage_sorted if x["priority"] == "high_attention"]
    watch = [x for x in triage_sorted if x["priority"] == "watch"]
    low = [x for x in triage_sorted if x["priority"] == "low_priority"]

    # Deterministic plain-language conclusions
    strongest_theme = max(
        themes.items(),
        key=lambda kv: (kv[1]["avg_sma20_gap_pct"] if kv[1]["avg_sma20_gap_pct"] is not None else -999.0),
    )[0]
    weakest_theme = min(
        themes.items(),
        key=lambda kv: (kv[1]["avg_sma20_gap_pct"] if kv[1]["avg_sma20_gap_pct"] is not None else 999.0),
    )[0]

    high_names = ", ".join(x["ticker"] for x in high_attention[:3]) or "none"
    watch_names = ", ".join(x["ticker"] for x in watch[:3]) or "none"
    weak_names = ", ".join(x["ticker"] for x in low[-3:]) or "none"

    conclusions: List[str] = [
        f"Regime is {regime.replace('_', ' ')} with composite score {_round(composite, 1)} (breadth {_round(breadth_score,1)}, momentum {_round(momentum_score,1)}, volatility {_round(volatility_score,1)}).",
        f"Breadth shows {above20}/{valid} above SMA20 and {above50}/{valid} above SMA50.",
        f"Momentum is {'supportive' if avg_rsi >= 52 else 'soft'} with average RSI {_round(avg_rsi,1)}.",
        f"Volatility proxy averages {_round(avg_atr_pct,2)}% ATR/price ({'contained' if avg_atr_pct <= 3.2 else 'elevated'}).",
        f"Strongest theme by SMA20 gap proxy: {strongest_theme}; weakest: {weakest_theme}.",
        f"Triage is concentrated in {len(high_attention)} high-attention names ({high_names}) and {len(watch)} watch names ({watch_names}).",
        f"Weakest near-term setups are concentrated in {weak_names}; avoid broad aggression while the regime stays {regime.replace('_', ' ')}.",
        f"Signal quality: missing field rate {_round((missing_fields/field_slots)*100.0,1)}%, stale-indicator rate {_round((stale_count/max(total,1))*100.0,1)}%.",
    ]

    if len(high_attention) >= 5:
        conclusions.append("Action bias: prioritize high_attention names first before broad watchlist review.")
    elif len(high_attention) > 0:
        conclusions.append(f"Action bias: focus first on {high_names} before spending time on the low-priority tail.")
    else:
        conclusions.append(f"Action bias: no clear leadership; keep attention on {watch_names} and wait for confirmation.")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_generated_at": signals_doc.get("generated_at") if isinstance(signals_doc, dict) else None,
        "inputs": {"signals_total": total, "signals_valid": valid},
        "market_regime": {
            "label": regime,
            "composite_score": _round(composite, 2),
            "components": {
                "breadth": _round(breadth_score, 2),
                "momentum": _round(momentum_score, 2),
                "volatility": _round(volatility_score, 2),
            },
            "metrics": {
                "above_sma20": above20,
                "above_sma50": above50,
                "avg_rsi14": _round(avg_rsi, 2),
                "avg_atr_pct_of_price": _round(avg_atr_pct, 3),
            },
        },
        "themes": themes,
        "signal_quality": {
            "missing_fields": missing_fields,
            "field_slots": field_slots,
            "missing_data_pct": _round((missing_fields / field_slots) * 100.0, 2),
            "stale_indicator_count": stale_count,
            "stale_indicator_pct": _round((stale_count / max(total, 1)) * 100.0, 2),
        },
        "triage": {
            "high_attention": high_attention,
            "watch": watch,
            "low_priority": low,
            "ranked": triage_sorted,
        },
        "conclusions": conclusions[:8],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build atlas_deep_analysis.json from local signals")
    ap.add_argument("--input", default="data/cache/signals_local.json")
    ap.add_argument("--output", default="data/cache/atlas_deep_analysis.json")
    args = ap.parse_args()

    src = Path(args.input)
    dst = Path(args.output)
    if not src.exists():
        raise FileNotFoundError(f"Missing input file: {src}")

    doc = json.loads(src.read_text(encoding="utf-8"))
    out = build(doc)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
