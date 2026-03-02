#!/usr/bin/env python3
"""Build compact Atlas local intelligence snapshot from signals_local.json."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _num(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _round(v: Optional[float], digits: int = 2) -> Optional[float]:
    if v is None:
        return None
    return round(v, digits)


def _signal_tags(close: Optional[float], sma20: Optional[float], rsi14: Optional[float]) -> List[str]:
    tags: List[str] = []
    if close is not None and sma20 is not None:
        tags.append("trend_up" if close >= sma20 else "trend_down")
    if rsi14 is not None:
        if rsi14 >= 60:
            tags.append("momentum_hot")
        elif rsi14 <= 40:
            tags.append("momentum_cold")
    return tags


def build_snapshot(signals_doc: Dict[str, Any], top_n: int = 5) -> Dict[str, Any]:
    signals = signals_doc.get("signals", {}) if isinstance(signals_doc, dict) else {}

    valid_rows: List[Dict[str, Any]] = []
    per_ticker: Dict[str, Dict[str, Any]] = {}

    above_sma20 = 0
    above_sma50 = 0
    rsi_values: List[float] = []
    overbought = 0
    oversold = 0

    movers: List[Dict[str, Any]] = []
    volatility: List[Dict[str, Any]] = []

    for ticker, row in signals.items():
        if not isinstance(row, dict) or not row.get("ok"):
            per_ticker[ticker] = {"ok": False, "tags": ["data_unavailable"]}
            continue

        latest = row.get("latest", {}) or {}
        ind = row.get("indicators", {}) or {}

        close = _num(latest.get("close"))
        sma20 = _num(ind.get("sma20"))
        sma50 = _num(ind.get("sma50"))
        rsi14 = _num(ind.get("rsi14"))
        atr14 = _num(ind.get("atr14"))

        tags = _signal_tags(close, sma20, rsi14)
        per_ticker[ticker] = {
            "ok": True,
            "close": _round(close, 4),
            "sma20": _round(sma20, 4),
            "rsi14": _round(rsi14, 2),
            "tags": tags,
        }

        valid_rows.append({
            "ticker": ticker,
            "close": close,
            "sma20": sma20,
            "sma50": sma50,
            "rsi14": rsi14,
            "atr14": atr14,
        })

        if close is not None and sma20 is not None and sma20 != 0:
            gap_pct = (close - sma20) / sma20 * 100.0
            movers.append({"ticker": ticker, "close_vs_sma20_pct": _round(gap_pct, 2)})
            if close >= sma20:
                above_sma20 += 1

        if close is not None and sma50 is not None:
            if close >= sma50:
                above_sma50 += 1

        if rsi14 is not None:
            rsi_values.append(rsi14)
            if rsi14 >= 70:
                overbought += 1
            elif rsi14 <= 30:
                oversold += 1

        if close is not None and close != 0 and atr14 is not None:
            atr_pct = atr14 / close * 100.0
            volatility.append({"ticker": ticker, "atr14_pct_of_close": _round(atr_pct, 2)})

    movers_sorted = sorted(movers, key=lambda x: abs(x["close_vs_sma20_pct"]), reverse=True)[:top_n]
    vol_sorted = sorted(volatility, key=lambda x: x["atr14_pct_of_close"], reverse=True)[:top_n]

    valid_count = len(valid_rows)
    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_generated_at": signals_doc.get("generated_at") if isinstance(signals_doc, dict) else None,
        "count": {
            "total": len(signals),
            "valid": valid_count,
            "invalid": max(0, len(signals) - valid_count),
        },
        "breadth": {
            "above_sma20": above_sma20,
            "above_sma50": above_sma50,
            "universe": valid_count,
        },
        "risk": {
            "avg_rsi14": _round(sum(rsi_values) / len(rsi_values), 2) if rsi_values else None,
            "overbought_rsi70": overbought,
            "oversold_rsi30": oversold,
            "rsi_universe": len(rsi_values),
        },
        "top_movers_proxy": movers_sorted,
        "top_volatility": vol_sorted,
        "signals": per_ticker,
    }
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Build atlas_snapshot.json from local signals")
    parser.add_argument("--input", default="data/cache/signals_local.json", help="Path to signals_local.json")
    parser.add_argument("--output", default="data/cache/atlas_snapshot.json", help="Output snapshot path")
    parser.add_argument("--top-n", type=int, default=5, help="Top N entries for movers/volatility")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Missing input file: {input_path}")

    doc = json.loads(input_path.read_text(encoding="utf-8"))
    snapshot = build_snapshot(doc, top_n=max(1, args.top_n))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
